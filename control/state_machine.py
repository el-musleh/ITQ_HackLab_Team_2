#!/usr/bin/env python3
"""
State Machine — Main FSM for autonomous ball collection.

States: STARTUP → SEARCH → APPROACH → COLLECT → RETURN → DEPOSIT → SEARCH
Handles transitions based on perception input and timeouts.
"""

import time
from enum import Enum


class State(Enum):
    """Robot states."""
    STARTUP = "startup"
    SEARCH = "search"
    APPROACH = "approach"
    COLLECT = "collect"
    RETURN = "return"
    DEPOSIT = "deposit"
    AVOID_BOUNDARY = "avoid_boundary"
    AVOID_OBSTACLE = "avoid_obstacle"
    STOPPED = "stopped"


class StateMachine:
    """Finite state machine for autonomous ball collection."""
    
    def __init__(self, config=None):
        """
        Initialize state machine.
        
        Args:
            config: Optional configuration dict
        """
        self.state = State.STARTUP
        self.previous_state = None
        
        # State entry time (for timeouts)
        self.state_entry_time = time.time()
        
        # Timeouts (seconds)
        self.search_timeout = 10.0  # Give up searching after 10s
        self.approach_timeout = 5.0  # Give up approaching after 5s
        self.collect_timeout = 3.0   # Arm motion timeout
        self.return_timeout = 10.0   # Return to basket timeout
        self.avoid_timeout = 2.0     # Avoidance maneuver timeout
        
        # Cooldown after avoidance (prevent rapid re-triggering)
        self.avoidance_cooldown = 1.0
        self.last_avoidance_time = 0
        
        # Target tracking
        self.target_ball = None  # (color, centroid, distance, area)
        self.balls_collected = 0
        
        # Flags
        self.basket_calibrated = False
        self.has_ball = False
    
    def update(self, perception_data):
        """
        Update state machine based on perception input.
        
        Args:
            perception_data: Dict with keys:
                - 'balls': List of detected balls
                - 'obstacle': Obstacle detection result dict
                - 'basket': Basket detection result dict
                
        Returns:
            Dict with action commands:
            {
                'state': current State,
                'action': str (motor command),
                'target': target info or None,
                'message': str (status message)
            }
        """
        current_time = time.time()
        time_in_state = current_time - self.state_entry_time
        
        # Extract perception data
        balls = perception_data.get('balls', [])
        obstacle = perception_data.get('obstacle', {})
        basket = perception_data.get('basket', {})
        
        # Priority 1: Boundary avoidance (always takes priority)
        if self._should_avoid_boundary(obstacle, current_time):
            return self._transition_to_avoid_boundary(obstacle)
        
        # Priority 2: Obstacle avoidance
        if self._should_avoid_obstacle(obstacle, current_time):
            return self._transition_to_avoid_obstacle(obstacle)
        
        # State-specific logic
        if self.state == State.STARTUP:
            return self._handle_startup(basket)
        
        elif self.state == State.SEARCH:
            return self._handle_search(balls, time_in_state)
        
        elif self.state == State.APPROACH:
            return self._handle_approach(balls, time_in_state)
        
        elif self.state == State.COLLECT:
            return self._handle_collect(time_in_state)
        
        elif self.state == State.RETURN:
            return self._handle_return(basket, time_in_state)
        
        elif self.state == State.DEPOSIT:
            return self._handle_deposit(time_in_state)
        
        elif self.state == State.AVOID_BOUNDARY:
            return self._handle_avoid_boundary(time_in_state)
        
        elif self.state == State.AVOID_OBSTACLE:
            return self._handle_avoid_obstacle(time_in_state)
        
        elif self.state == State.STOPPED:
            return self._handle_stopped()
        
        else:
            return self._create_response('stop', 'Unknown state')
    
    def _should_avoid_boundary(self, obstacle, current_time):
        """Check if boundary avoidance should trigger."""
        if self.state == State.STOPPED:
            return False
        
        # Cooldown check
        if current_time - self.last_avoidance_time < self.avoidance_cooldown:
            return False
        
        return obstacle.get('boundary_detected', False)
    
    def _should_avoid_obstacle(self, obstacle, current_time):
        """Check if obstacle avoidance should trigger."""
        if self.state == State.STOPPED:
            return False
        
        # Don't avoid during collection or deposit
        if self.state in [State.COLLECT, State.DEPOSIT]:
            return False
        
        # Cooldown check
        if current_time - self.last_avoidance_time < self.avoidance_cooldown:
            return False
        
        return obstacle.get('obstacle_detected', False)
    
    def _transition_to_avoid_boundary(self, obstacle):
        """Transition to boundary avoidance."""
        self._change_state(State.AVOID_BOUNDARY)
        self.last_avoidance_time = time.time()
        
        turn_dir = obstacle.get('turn_direction', 'reverse')
        return self._create_response('avoid_boundary', 
                                     f'BOUNDARY! Turn {turn_dir}',
                                     {'direction': turn_dir})
    
    def _transition_to_avoid_obstacle(self, obstacle):
        """Transition to obstacle avoidance."""
        self._change_state(State.AVOID_OBSTACLE)
        self.last_avoidance_time = time.time()
        
        turn_dir = obstacle.get('turn_direction', 'reverse')
        return self._create_response('avoid_obstacle',
                                     f'OBSTACLE! Turn {turn_dir}',
                                     {'direction': turn_dir})
    
    def _handle_startup(self, basket):
        """Handle STARTUP state."""
        if basket.get('basket_found', False):
            self.basket_calibrated = True
            self._change_state(State.SEARCH)
            return self._create_response('stop', 'Basket found, starting search')
        else:
            return self._create_response('stop', 
                                        'STARTUP: Waiting for basket calibration')
    
    def _handle_search(self, balls, time_in_state):
        """Handle SEARCH state."""
        if time_in_state > self.search_timeout:
            # Timeout: rotate to scan
            return self._create_response('rotate', 'Searching for balls...')
        
        if balls:
            # Ball found, select closest
            self.target_ball = balls[0]  # Already sorted by distance
            self._change_state(State.APPROACH)
            return self._create_response('stop', 
                                        f'Ball found: {self.target_ball[0]}',
                                        self.target_ball)
        
        # Keep searching (rotate slowly)
        return self._create_response('rotate', 'Searching for balls...')
    
    def _handle_approach(self, balls, time_in_state):
        """Handle APPROACH state."""
        if time_in_state > self.approach_timeout:
            # Timeout: ball lost, return to search
            self.target_ball = None
            self._change_state(State.SEARCH)
            return self._create_response('stop', 'Approach timeout, resuming search')
        
        # Check if target ball still visible
        target_visible = False
        if self.target_ball and balls:
            target_color = self.target_ball[0]
            for ball in balls:
                if ball[0] == target_color:
                    # Update target with latest position
                    self.target_ball = ball
                    target_visible = True
                    break
        
        if not target_visible:
            # Ball lost
            self.target_ball = None
            self._change_state(State.SEARCH)
            return self._create_response('stop', 'Ball lost, resuming search')
        
        # Check if close enough to collect
        distance = self.target_ball[2]
        if distance < 15:  # Within 15 cm
            self._change_state(State.COLLECT)
            return self._create_response('stop', 'Close enough, collecting...')
        
        # Continue approaching
        return self._create_response('approach', 
                                     f'Approaching {self.target_ball[0]} ball',
                                     self.target_ball)
    
    def _handle_collect(self, time_in_state):
        """Handle COLLECT state."""
        if time_in_state > self.collect_timeout:
            # Collection complete (or timeout)
            self.has_ball = True
            self.target_ball = None
            self._change_state(State.RETURN)
            return self._create_response('stop', 'Collection complete, returning to basket')
        
        # Arm is collecting
        return self._create_response('collect', 'Collecting ball...')
    
    def _handle_return(self, basket, time_in_state):
        """Handle RETURN state."""
        if time_in_state > self.return_timeout:
            # Timeout: basket lost, search for it
            return self._create_response('rotate', 'Searching for basket...')
        
        if not basket.get('basket_found', False):
            # Basket not visible, rotate to find it
            return self._create_response('rotate', 'Searching for basket...')
        
        # Check if close enough to deposit
        distance = basket.get('distance', 999)
        if distance < 20:  # Within 20 cm
            self._change_state(State.DEPOSIT)
            return self._create_response('stop', 'At basket, depositing...')
        
        # Continue returning
        return self._create_response('return', 
                                     f'Returning to basket ({distance:.0f} cm)',
                                     basket)
    
    def _handle_deposit(self, time_in_state):
        """Handle DEPOSIT state."""
        if time_in_state > 2.0:  # Deposit takes ~2 seconds
            # Deposit complete
            self.has_ball = False
            self.balls_collected += 1
            self._change_state(State.SEARCH)
            return self._create_response('stop', 
                                        f'Deposit complete! Total: {self.balls_collected}')
        
        # Arm is depositing
        return self._create_response('deposit', 'Depositing ball...')
    
    def _handle_avoid_boundary(self, time_in_state):
        """Handle AVOID_BOUNDARY state."""
        if time_in_state > self.avoid_timeout:
            # Avoidance complete, return to previous state
            if self.previous_state == State.APPROACH and self.target_ball:
                self._change_state(State.APPROACH)
            else:
                self._change_state(State.SEARCH)
            return self._create_response('stop', 'Boundary avoided, resuming')
        
        return self._create_response('avoid', 'Avoiding boundary...')
    
    def _handle_avoid_obstacle(self, time_in_state):
        """Handle AVOID_OBSTACLE state."""
        if time_in_state > self.avoid_timeout:
            # Avoidance complete, return to previous state
            if self.previous_state == State.APPROACH and self.target_ball:
                self._change_state(State.APPROACH)
            else:
                self._change_state(State.SEARCH)
            return self._create_response('stop', 'Obstacle avoided, resuming')
        
        return self._create_response('avoid', 'Avoiding obstacle...')
    
    def _handle_stopped(self):
        """Handle STOPPED state."""
        return self._create_response('stop', 'Robot stopped (manual intervention required)')
    
    def _change_state(self, new_state):
        """Change to a new state."""
        self.previous_state = self.state
        self.state = new_state
        self.state_entry_time = time.time()
    
    def _create_response(self, action, message, target=None):
        """Create response dict."""
        return {
            'state': self.state,
            'action': action,
            'target': target,
            'message': message,
            'balls_collected': self.balls_collected
        }
    
    def emergency_stop(self):
        """Emergency stop (e.g., manual override)."""
        self._change_state(State.STOPPED)
    
    def reset(self):
        """Reset state machine to SEARCH."""
        self.state = State.SEARCH
        self.previous_state = None
        self.state_entry_time = time.time()
        self.target_ball = None
        self.has_ball = False
    
    def get_status(self):
        """Get current status summary."""
        return {
            'state': self.state.value,
            'balls_collected': self.balls_collected,
            'has_ball': self.has_ball,
            'target': self.target_ball,
            'basket_calibrated': self.basket_calibrated
        }
