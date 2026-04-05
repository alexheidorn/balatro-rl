"""
Balatro RL Environment
Wraps the pipe-based communication with Balatro mod in a standard RL interface.
This acts as a translator between Balatro's JSON pipe communication and 
RL libraries that expect gym-style step()/reset() methods.
"""

import numpy as np
from typing import Dict, Any, Tuple, List, Optional
import logging
import os
import gymnasium as gym
from .. import global_var
from gymnasium import spaces
from ..utils.communication import BalatroPipeIO, BalatroSocketIO
from .reward import BalatroRewardCalculator
from ..utils.mappers import BalatroStateMapper, BalatroActionMapper
from ..utils.replay import ReplaySystem


class BalatroEnv(gym.Env):
    """
    Standard RL Environment wrapper for Balatro
    
    Translates between:
    - Balatro mod's JSON pipe communication (/tmp/balatro_request, /tmp/balatro_response)
    - Standard RL interface (step, reset, observation spaces)
    
    This allows RL libraries like Stable-Baselines3 to train on Balatro
    without knowing about the underlying pipe communication system.
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_state = None
        self.prev_state = None
        self.game_over = False
        self.restart_pending = False
        #Change this to change the seed
        self.seed = global_var.choosen_seed

        # Initialize communication system — swap transport based on env var
        if os.getenv("BALATRO_COMM_MODE") == "socket":
            self.logger.info("Using socket communication")
            self.pipe_io = BalatroSocketIO(port=int(os.getenv("BALATRO_SOCKET_PORT", 9000)))
        else:
            self.logger.info("Using pipe communication")
            self.pipe_io = BalatroPipeIO()
        
        # Initialize reward systems
        self.reward_calculator = BalatroRewardCalculator()

        # Replay System
        self.replay_system = ReplaySystem()
        self.actions_taken = []

        self.slices = {
            "action_selection": slice(0,1),
        }

        # Define Gymnasium spaces
        # Action Spaces; This should describe the type and shape of the action
        # Constants - Core gameplay actions only (SELECT_HAND=1, PLAY_HAND=2, DISCARD_HAND=3)
        self.MAX_ACTIONS = 11
        self.MAX_CARDS = 8  # Max cards in hand
        self.MAX_SHOP_SLOTS = 5
        self.MAX_JOKER_SLOTS = 5
        action_selection = np.array([self.MAX_ACTIONS])
        card_indices = np.array([2] * self.MAX_CARDS) # 8 cards, each can be selected (1) or not (0) #TODO can we or have we already masked card selection?
        shop_slot = np.array([self.MAX_SHOP_SLOTS])
        joker_slot = np.array([self.MAX_JOKER_SLOTS])

        self.action_space = spaces.MultiDiscrete(np.concatenate([
            action_selection,
            card_indices, shop_slot, joker_slot
        ]))
        ACTION_SLICE_LAYOUT = [
            ("action_selection", 1),
            ("card_indices", self.MAX_CARDS),
            ("shop_slot", 1),
            ("joker_slot", 1),
        ]
        slices = self._build_action_slices(ACTION_SLICE_LAYOUT)
        
        # Observation space: This should describe the type and shape of the observation
        # Constants
        self.OBSERVATION_SIZE = 313
        self.observation_space = spaces.Box(
            low=-np.inf, # lowest bound of observation data
            high=np.inf, # highest bound of observation data
            shape=(self.OBSERVATION_SIZE,), # Adjust based on actual state size which  This is a 1D array 
            dtype=np.float32 # Data type of the numbers
        )

        # Initialize mappers
        self.state_mapper = BalatroStateMapper(observation_size=self.OBSERVATION_SIZE, max_actions=self.MAX_ACTIONS)
        self.action_mapper = BalatroActionMapper(action_slices=slices)
    def _detect_phase(self, request):
        current_game_state = request.get('game_state', {})
        current_game_state_ID = current_game_state.get('state', 0)

        if current_game_state_ID == 5:
            # print("Blind Beaten!")
            global_var.isShop = True
            global_var.isBlind = False
        else:
            global_var.isShop = False
            global_var.isBlind = True
    def reset(self, seed=None, options=None):
        """
        Reset the environment for a new episode
        
        In Balatro context, this means starting a new run.
        Communicates with Balatro mod via pipes to initiate reset.
        
        Returns:
            Initial observation/game state
        """
        self.current_state = None
        self.prev_state = None
        self.game_over = False
        self.actions_taken = []
        
        if self.restart_pending:
            self.restart_pending = False
            restart_response = {"action": 6, "params": [], "seed": self.seed}
            self.pipe_io.send_response(restart_response)

        # Reset reward tracking
        self.reward_calculator.reset()
        
        # Wait for initial request from Balatro (game start)
        initial_request = self.pipe_io.wait_for_request()
        if not initial_request:
            raise RuntimeError("Failed to receive initial request from Balatro")
        
        while initial_request.get('game_state', {}).get('state') == 4:
            restart_response = {"action": 6, "params": [], "seed": self.seed}

            self.pipe_io.send_response(restart_response)
            initial_request = self.pipe_io.wait_for_request()
            if not initial_request:
                raise RuntimeError("Failed to receive initial request from Balatro after restart")
        # Process initial state for SB3
        self.current_state = initial_request
        self._detect_phase(initial_request)
        initial_observation = self.state_mapper.process_game_state(self.current_state)
        
        # Create initial action mask
        initial_available_actions = initial_request.get('available_actions', [])
        initial_action_mask = self._create_action_mask(initial_available_actions, self.current_state)
        self._action_masks = initial_action_mask
        
        return initial_observation, {}
    
    def step(self, action):
        """
        Take an action in the Balatro environment
        Sends action to Balatro mod via JSON pipe, waits for response,
        calculates reward, and returns standard RL step format.
        
        Args:
            action: Action dictionary (e.g., {"action": 1, "params": {...}})
            
        Returns:
            Tuple of (observation, reward, done, info) where:
            - observation: Processed game state for neural network
            - reward: Calculated reward for this step
            - done: Whether episode is finished (game over)
            - info: Additional debug information
        """
        # Store previous state for reward calculation
        self.prev_state = self.current_state

        state_id = self.current_state.get('game_state', {1}).get('state', 0)

        if state_id == 8:
        # Force action selection to CASH_OUT if it isn't already
            action[self.slices["action_selection"]] = [10]
        
        # Send action response to Balatro mod
        response_data = self.action_mapper.process_action(rl_action=action)
        self.actions_taken.append(response_data)
        success = self.pipe_io.send_response(response_data)
        if not success:
            raise RuntimeError("Failed to send response to Balatro")
        
        # Wait for next request with new game state
        next_request = self.pipe_io.wait_for_request()
        if next_request:
            state_id = next_request.get('game_state', {}).get('state', 0)
                        
            if state_id == 8:
                import time
                time.sleep(0.1)
        if not next_request:
            self.game_over = True
            observation = self.state_mapper.process_game_state(self.current_state)
            reward = 0.0
            return observation, reward, True, False, {"timeout": True}
        self.logger.info(f"Received request, state: {next_request.get('game_state', {}).get('state', '?')}, actions: {next_request.get('available_actions', [])}")
        
        #Check for Game Over
        game_state_early = next_request.get('game_state', {})
        if game_state_early.get('game_over', 0) == 1:
            observation = self.state_mapper.process_game_state(self.current_state)
            reward = self.reward_calculator.calculate_reward(
                current_state=self.current_state,
                prev_state=self.prev_state or {},
                phase=self.current_state,
            )
            self.restart_pending = True
            return observation, reward, True, False, {
                "ante": game_state_early.get('ante', 0),
                "round": game_state_early.get('round_count', 0),
                "chips": game_state_early.get('chips', 0),
                "won": False,
                "jokers": game_state_early.get('jokers', [])
                }
        while next_request.get('game_state', {}).get('state') == 4:
            self.logger.info("Auto-handling START_RUN state, sending restart")
            restart_response = {"action": 6, "params": [], "seed": self.seed}

            self.pipe_io.send_response(restart_response)
            next_request = self.pipe_io.wait_for_request()
            if not next_request:
                return (
                    self.state_mapper.process_game_state(self.current_state),
                    0.0, True, False, {"timeout": True}
                )
            self.logger.info(
                f"Received request, state: {next_request.get('game_state', {}).get('state', '?')}, "
                f"actions: {next_request.get('available_actions', [])}"
            )
        # Update current state
        self.current_state = next_request
        is_endless_enabled = self.current_state.get('auto_endless_config', False)
        self._detect_phase(next_request)
        game_state = self.current_state.get('game_state', {})
        jokers = game_state.get('jokers', [])
        
        # Check for game win condition
        game_win_flag = game_state.get('game_win', 0)
        if game_win_flag == 1:
            observation = self.state_mapper.process_game_state(self.current_state)
            reward = self.reward_calculator.calculate_reward(
                current_state=self.current_state,
                prev_state=self.prev_state or {},
                phase=self.current_state,
            )

            # Save replay
            self.replay_system.try_save_replay(
                file_path=self.replay_system.REPLAY_FILE_PATH,
                seed=game_state.get('seed', ''),
                actions=self.actions_taken,
                score=reward,
                chips=game_state.get('chips', 0)
            )
            terminated = not is_endless_enabled 

            return observation, reward, terminated, False, {
                "ante": game_state.get('ante', 0),
                "round": game_state.get('round_count', 0),
                "chips": game_state.get('chips', 0),
                "won": True,
                "jokers": jokers,
                "win_detected": True, 
                "is_endless": is_endless_enabled
            }
        # Process new state for SB3
        observation = self.state_mapper.process_game_state(self.current_state)
        # Calculate reward using expert reward calculator
        reward = self.reward_calculator.calculate_reward(
            current_state=self.current_state,
            prev_state=self.prev_state if self.prev_state else {}
        )
        done = False
            
        terminated = done
        truncated = False 
        
        # Create action mask for MaskablePPO
        info = {}
        try:
            available_actions = next_request.get('available_actions', [])
            action_mask = self._create_action_mask(available_actions, self.current_state)
            self._action_masks = action_mask
        except Exception as e:
            self.logger.error(f"Action mask error: {e}", exc_info=True)
            self._action_masks = np.ones(sum(self.action_space.nvec), dtype=bool)

        return observation, reward, terminated, truncated, info

    def cleanup(self):
        """
        Clean up environment resources
        
        Call this when shutting down to clean up pipe communication.
        """
        self.pipe_io.cleanup()

    # Action Masks for MaskablePPO and for ActionWrapper
    def action_masks(self):
        """Required method for MaskablePPO"""
        if hasattr(self, '_action_masks') and self._action_masks is not None:
            mask = np.array(self._action_masks, dtype=bool)
            expected = sum(self.action_space.nvec)
            assert len(mask) == expected, (
                f"Mask length {len(mask)} != expected {expected}. "
            )
            return mask
    
        # Safe fallback: allow all actions
        return np.ones(sum(self.action_space.nvec), dtype=bool)
    
    def _create_action_mask(self, available_actions, current_game_state):
        """Create action mask for MultiDiscrete space"""
        action_masks = []
        state_id = current_game_state.get('game_state', {}).get('state', 0)
    
        action_selection_mask = [False] * self.MAX_ACTIONS
        balatro_to_ai_mapping = {
            1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 
            7: 6, 8: 7, 9: 8, 10: 9, 11: 10
        }

        if state_id == 8:
            action_selection_mask[10] = True
        else:
            for action_id in available_actions:
                if action_id in balatro_to_ai_mapping:
                    ai_index = balatro_to_ai_mapping[action_id]
                    action_selection_mask[ai_index] = True
                    
        action_masks.append(action_selection_mask)

        if state_id == 8:
            # ROUND_EVAL: Disable everything but the action itself
            for _ in range(self.MAX_CARDS):
                action_masks.append([True, False])
            action_masks.append([False] * self.MAX_SHOP_SLOTS)
            action_masks.append([False] * self.MAX_JOKER_SLOTS)

        elif global_var.isShop:
            # SHOP: Disable cards, enable shop slots based on money
            for _ in range(self.MAX_CARDS):
                action_masks.append([True, False]) 
        
            inner_state = current_game_state.get('game_state', {})
            current_shop_items = inner_state.get('shop', {}).get('items', [])
            money = inner_state.get('gold', 0)
        
            shop_masks = [False] * self.MAX_SHOP_SLOTS
            for i, item in enumerate(current_shop_items):
                if i < self.MAX_SHOP_SLOTS and item.get('cost', 999) <= money:
                    shop_masks[i] = True
            action_masks.append(shop_masks)

            avaliable_jokers = inner_state.get('jokers', [])
            joker_mask = [False] * self.MAX_JOKER_SLOTS
            for i in range(min(len(avaliable_jokers), self.MAX_JOKER_SLOTS)):
                joker_mask[i] = True
            action_masks.append(joker_mask)

            if 10 in available_actions:
                # Check if we are in a transition state
                pass
            if state_id == 5:
                if self.actions_taken and self.actions_taken[-1].get('action') == 10:
                    action_selection_mask[9] = False

        else:
            # BLIND/HAND: Handle Card Selection
            # If PLAY or DISCARD is available, cards should already be selected 
            # (or AI shouldn't select more), otherwise allow selection.
            can_select = not any(a in [2, 3] for a in available_actions)
            for _ in range(self.MAX_CARDS):
                action_masks.append([True, True] if can_select else [True, False])
            
            action_masks.append([False] * self.MAX_SHOP_SLOTS)
            action_masks.append([False] * self.MAX_JOKER_SLOTS)

        flat = [item for sublist in action_masks for item in sublist]
        return flat


    @staticmethod
    def _build_action_slices(layout: List[Tuple[str, int]]) -> Dict[str, slice]:
        """
        Create slices for our actions so that we can precisely extract the
        right params to send over to balatro
        
        Args:
            layout: Our ACTION_SLICE_LAYOUT that contains action name and size
        Return:
            A dictionary containing a key being our action space slice name, and  
            the slice 
        """
        slices = {}
        start = 0
        for action_name, size in layout:
            slices[action_name] = slice(start, start + size)
            start += size
        return slices
