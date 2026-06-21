"""
PyBullet Simulation Core
Initializes physics engine, loads models, and manages simulation loop
"""

import pybullet as p
import pybullet_data
import numpy as np
import os
import time


class SimulationCore:
    """Core simulation manager for PyBullet"""
    
    def __init__(self, gui=True, real_time=False):
        """
        Initialize PyBullet simulation
        
        Args:
            gui: Show PyBullet GUI window
            real_time: Run at real-time speed (vs. as fast as possible)
        """
        self.gui = gui
        self.real_time = real_time
        self.physics_client = None
        self.robot_id = None
        self.arena_id = None
        self.ball_ids = []
        self.time_step = 1.0 / 240.0  # 240 Hz physics
        
        # Get paths
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.models_path = os.path.join(self.base_path, 'simulation', 'models')
        
    def initialize(self):
        """Initialize PyBullet physics engine"""
        if self.gui:
            self.physics_client = p.connect(p.GUI)
        else:
            self.physics_client = p.connect(p.DIRECT)
        
        # Set additional search path for PyBullet data
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        # Configure physics
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(self.time_step)
        p.setRealTimeSimulation(0)  # We'll step manually
        
        print(f"[SimCore] PyBullet initialized (GUI: {self.gui})")
        
    def load_arena(self):
        """Load arena model (floor, walls, obstacles, basket)"""
        arena_urdf = os.path.join(self.models_path, 'arena.urdf')
        
        if not os.path.exists(arena_urdf):
            raise FileNotFoundError(f"Arena URDF not found: {arena_urdf}")
        
        # Load arena at ground level
        self.arena_id = p.loadURDF(
            arena_urdf,
            basePosition=[0, 0, 0],
            baseOrientation=[0, 0, 0, 1],
            useFixedBase=True
        )
        
        print(f"[SimCore] Arena loaded (ID: {self.arena_id})")
        
    def load_robot(self, start_pos=[0, 0, 0.15], start_orientation=[0, 0, 0]):
        """
        Load robot model
        
        Args:
            start_pos: [x, y, z] starting position in meters
            start_orientation: [roll, pitch, yaw] in radians
        """
        robot_urdf = os.path.join(self.models_path, 'jetank.urdf')
        
        if not os.path.exists(robot_urdf):
            raise FileNotFoundError(f"Robot URDF not found: {robot_urdf}")
        
        # Convert orientation to quaternion
        quat = p.getQuaternionFromEuler(start_orientation)
        
        # Load robot
        self.robot_id = p.loadURDF(
            robot_urdf,
            basePosition=start_pos,
            baseOrientation=quat,
            useFixedBase=False
        )
        
        # Get joint info
        self.num_joints = p.getNumJoints(self.robot_id)
        print(f"[SimCore] Robot loaded (ID: {self.robot_id}, Joints: {self.num_joints})")
        
        # Print joint names for debugging
        for i in range(self.num_joints):
            joint_info = p.getJointInfo(self.robot_id, i)
            print(f"  Joint {i}: {joint_info[1].decode('utf-8')} (Type: {joint_info[2]})")
        
        return self.robot_id
        
    def spawn_balls(self, num_balls=22, colors=['blue', 'red', 'silver']):
        """
        Spawn colored balls randomly in arena
        
        Args:
            num_balls: Number of balls to spawn
            colors: List of color names to distribute
        """
        # Color mapping (RGB)
        color_map = {
            'blue': [0.2, 0.4, 1.0, 1],
            'red': [1.0, 0.2, 0.2, 1],
            'silver': [0.8, 0.8, 0.8, 1]
        }
        
        ball_radius = 0.02  # 2cm radius (4cm diameter)
        
        # Spawn balls in random positions
        np.random.seed(42)  # Reproducible positions
        
        for i in range(num_balls):
            # Random position in arena (robot starts at 0,0 top-right corner)
            # Arena extends from (0,0) to (1.8, 1.75) in positive direction
            # Basket is at center (0.9, 0.875)
            x = np.random.uniform(0.2, 1.6)
            y = np.random.uniform(0.2, 1.5)
            
            # Avoid basket area (centered at 0.9, 0.875)
            basket_x, basket_y = 0.9, 0.875
            while np.sqrt((x - basket_x)**2 + (y - basket_y)**2) < 0.25:
                x = np.random.uniform(0.2, 1.6)
                y = np.random.uniform(0.2, 1.5)
            
            z = ball_radius + 0.01  # Slightly above ground
            
            # Create sphere collision shape
            col_shape = p.createCollisionShape(p.GEOM_SPHERE, radius=ball_radius)
            vis_shape = p.createVisualShape(
                p.GEOM_SPHERE,
                radius=ball_radius,
                rgbaColor=color_map[colors[i % len(colors)]]
            )
            
            # Spawn ball
            ball_id = p.createMultiBody(
                baseMass=0.005,  # 5g
                baseCollisionShapeIndex=col_shape,
                baseVisualShapeIndex=vis_shape,
                basePosition=[x, y, z]
            )
            
            self.ball_ids.append(ball_id)
        
        print(f"[SimCore] Spawned {num_balls} balls")
        
    def step(self):
        """Step physics simulation forward by one timestep"""
        p.stepSimulation()
        
        if self.real_time:
            time.sleep(self.time_step)
            
    def reset(self):
        """Reset simulation to initial state"""
        # Remove all balls
        for ball_id in self.ball_ids:
            p.removeBody(ball_id)
        self.ball_ids = []
        
        # Reset robot position
        if self.robot_id is not None:
            p.resetBasePositionAndOrientation(
                self.robot_id,
                [0, -0.6, 0.05],
                [0, 0, 0, 1]
            )
            
            # Reset joint positions
            for i in range(self.num_joints):
                p.resetJointState(self.robot_id, i, 0)
        
        # Respawn balls
        self.spawn_balls()
        
        print("[SimCore] Simulation reset")
        
    def get_robot_state(self):
        """Get current robot position and orientation"""
        if self.robot_id is None:
            return None
            
        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)
        
        return {
            'position': pos,
            'orientation': euler,
            'quaternion': orn
        }
        
    def check_collision(self, body_a, body_b):
        """Check if two bodies are in collision"""
        contact_points = p.getContactPoints(body_a, body_b)
        return len(contact_points) > 0
        
    def get_camera_view(self, width=320, height=240, fov=160):
        """
        Get camera view from robot's perspective
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            fov: Field of view in degrees
            
        Returns:
            RGB image as numpy array
        """
        if self.robot_id is None:
            return None
        
        # Get camera link position (joint index for camera)
        # For now, use base position + offset
        robot_state = self.get_robot_state()
        cam_pos = list(robot_state['position'])
        cam_pos[2] += 0.12  # Camera height offset
        
        # Camera looks forward and slightly down
        yaw = robot_state['orientation'][2]
        pitch = -0.2  # Look down 0.2 radians
        
        # Calculate target point
        target_dist = 1.0
        target = [
            cam_pos[0] + target_dist * np.cos(yaw),
            cam_pos[1] + target_dist * np.sin(yaw),
            cam_pos[2] - target_dist * np.sin(pitch)
        ]
        
        # Get camera image
        view_matrix = p.computeViewMatrix(
            cameraEyePosition=cam_pos,
            cameraTargetPosition=target,
            cameraUpVector=[0, 0, 1]
        )
        
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=fov,
            aspect=width / height,
            nearVal=0.01,
            farVal=10.0
        )
        
        # Render
        img_arr = p.getCameraImage(
            width, height,
            view_matrix,
            proj_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL
        )
        
        # Extract RGB (ignore alpha and depth)
        rgb = np.array(img_arr[2]).reshape(height, width, 4)[:, :, :3]
        
        return rgb
        
    def close(self):
        """Shutdown simulation"""
        if self.physics_client is not None:
            p.disconnect()
            print("[SimCore] Simulation closed")


if __name__ == "__main__":
    # Test simulation
    print("Testing SimulationCore...")
    
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    sim.load_robot()
    sim.spawn_balls(num_balls=22)
    
    print("\nRunning simulation for 5 seconds...")
    for i in range(1200):  # 5 seconds at 240 Hz
        sim.step()
        
        if i % 240 == 0:
            state = sim.get_robot_state()
            print(f"  t={i/240:.1f}s: pos={state['position']}")
    
    print("\nTest complete!")
    sim.close()
