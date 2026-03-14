--- RLBridge action registry module
--- Defines available AI actions, their conditions, and execution logic
--- Central registry for all possible AI interactions with the game

local input = require("input")
local utils = require("utils")
local ACTIONS = {}

-- Action constants (like G.STATES pattern)
-- Core gameplay actions are 1,2,3 for clean AI mapping
ACTIONS.SELECT_HAND = 1
ACTIONS.PLAY_HAND = 2
ACTIONS.DISCARD_HAND = 3
-- Auto-executed actions (not exposed to AI)
ACTIONS.START_RUN = 4
ACTIONS.SELECT_BLIND = 5
ACTIONS.RESTART_RUN = 6

ACTIONS.BUY_JOKER = 7
ACTIONS.SELL_JOKER = 8
ACTIONS.REROLL_SHOP = 9
ACTIONS.SKIP_SHOP = 10
ACTIONS.CASH_OUT = 11

-- Action mapping tables
local ACTION_IDS = {
    select_hand = ACTIONS.SELECT_HAND,
    play_hand = ACTIONS.PLAY_HAND,
    discard_hand = ACTIONS.DISCARD_HAND,
    start_run = ACTIONS.START_RUN,
    select_blind = ACTIONS.SELECT_BLIND,
    restart_run = ACTIONS.RESTART_RUN,
    buy_joker = ACTIONS.BUY_JOKER,
    sell_joker = ACTIONS.SELL_JOKER,
    reroll_shop = ACTIONS.REROLL_SHOP,
    skip_shop = ACTIONS.SKIP_SHOP,
    cash_out = ACTIONS.CASH_OUT
}

local ID_TO_ACTION = {
    [ACTIONS.SELECT_HAND] = "select_hand",
    [ACTIONS.PLAY_HAND] = "play_hand",
    [ACTIONS.DISCARD_HAND] = "discard_hand",
    [ACTIONS.START_RUN] = "start_run",
    [ACTIONS.SELECT_BLIND] = "select_blind",
    [ACTIONS.RESTART_RUN] = "restart_run",
    [ACTIONS.BUY_JOKER] = "buy_joker",
    [ACTIONS.SELL_JOKER] = "sell_joker",
    [ACTIONS.REROLL_SHOP] = "reroll_shop",
    [ACTIONS.SKIP_SHOP] = "skip_shop",
    [ACTIONS.CASH_OUT] = "cash_out"
}

-- Centralized action state tracking
local action_state = {}

--- Reset all action states (call when game state changes)
--- @return nil
function ACTIONS.reset_state()
    action_state = {}
end

--- Mark an action as executed
--- @param action_name string Name of the action that was executed
--- @return nil
function ACTIONS.mark_executed(action_name)
    action_state[action_name] = true
end

-- Action registry - defines what the AI can do and when
local action_registry = {
    start_run = {
        execute = function(params)
            return input.start_run()
        end,
        available_when = function()
            return G.STATE == G.STATES.MENU and not action_state.start_run
        end,
    },
    select_blind = {
        execute = function(params)
            return input.select_blind()
        end,
        available_when = function()
            return G.STATE == G.STATES.BLIND_SELECT and G.GAME.blind_on_deck ~= nil and not action_state.select_blind
        end,
    },
    select_hand = {
        execute = function(params)
            return input.select_hand(params)
        end,
        available_when = function()
            return G.STATE == G.STATES.SELECTING_HAND and G.hand and G.hand.cards and #G.hand.highlighted <= 0 and
                utils.is_game_ready_for_action() and
                not action_state.select_hand
        end,
    },
    play_hand = {
        execute = function(params)
            ACTIONS.reset_state()
            return input.play_hand()
        end,
        available_when = function()
            return G.STATE == G.STATES.SELECTING_HAND and G.hand and G.hand.cards and
                #G.hand.highlighted > 0 and utils.is_game_ready_for_action() and
                G.GAME.current_round.hands_left > 0 and  -- Must have hands left
                not action_state.play_hand
        end,
    },
    discard_hand = {
        execute = function(params)
            ACTIONS.reset_state()
            return input.discard_hand()
        end,
        available_when = function()
            return G.STATE == G.STATES.SELECTING_HAND and G.hand and G.hand.cards and
                #G.hand.highlighted > 0 and utils.is_game_ready_for_action() and
                G.GAME.current_round.discards_left > 0 and  -- Must have discards left
                not action_state.discard_hand
        end,
    },
    restart_run = {
        execute = function(params)
            return input.start_run()
        end,
        available_when = function()
            return (G.STATE == G.STATES.GAME_OVER) and not action_state.restart_run
        end,
    },
    buy_joker = {
        execute = function(params)
            local slot = params and params[1] or 1
            return input.buy_card(slot)
        end,
        available_when = function()
            return G.STATE == G.STATES.SHOP
                and G.SHOP and G.SHOP.jokers
                and #G.SHOP.jokers.cards > 0
        end,
    },
    sell_joker = {
        execute = function(params)
            local slot = params and params[1] or 1
            return input.sell_joker(slot)
        end,
        available_when = function()
            return G.STATE == G.STATES.SHOP
                and G.jokers and #G.jokers.cards > 0
        end,
    },
    reroll_shop = {
        execute = function(params)
            return input.reroll_shop()
        end,
        available_when = function()
            return G.STATE == G.STATES.SHOP
                and G.GAME.dollars >= G.GAME.current_round.reroll_cost
        end,
    },
    skip_shop = {
        execute = function(params)
            return input.skip_shop()
        end,
        available_when = function()
            return G.STATE == G.STATES.SHOP
        end,
    },
    cash_out = {
        execute = function(params)
            return input.cash_out()
        end,
        available_when = function()
            return G.STATE == G.STATES.ROUND_EVAL and G.STATE_COMPLETE and not action_state.cash_out
        end,
    },
}

--- Get all currently available actions
--- Checks each action in the registry and returns those that are available
--- @return table Available actions
function ACTIONS.get_available_actions()
    local available = {}

    for action_name, action_def in pairs(action_registry) do
        if action_def.available_when() then
            table.insert(available, ACTIONS.get_action_id(action_name))
        end
    end

    return available
end

--- Check if a specific action is available
--- Tests if the given action can be executed in the current game state
--- @param action_name string Name of the action to check
--- @return boolean True if action is available, false otherwise
function ACTIONS.is_action_available(action_name)
    local action_def = action_registry[action_name]
    return action_def and action_def.available_when()
end

--- Execute a specific action with given parameters
--- Validates availability and calls the action's execute function
--- @param action_id number ID of the action to execute
--- @param params table Parameters to pass to the action
--- @return table Result with success status and optional error message
function ACTIONS.execute_action(action_id, params)
    local action_name = ID_TO_ACTION[action_id]
    if not action_name then
        utils.log_input("ERROR: Invalid action ID: " .. tostring(action_id))
        return { success = false, error = "Invalid action ID" }
    end
    if not params then
        utils.log_input("ERROR: Invalid Params: " .. tostring(params))
        return { success = false, error = "Invalid params" }
    end

    utils.log_input("Executing action: " .. action_name)

    -- Validate action is available
    if not ACTIONS.is_action_available(action_name) then
        utils.log_input("ERROR: Action not available: " .. action_name)
        return { success = false, error = "Action not available" }
    end

    local action_def = action_registry[action_name]
    if action_def and action_def.execute then
        local result = action_def.execute(params)
        if result.success then
            if action_name == "cash_out" or action_name == "play_hand" or action_name == "discard_hand" then
                ACTIONS.reset_state()
            else
                ACTIONS.mark_executed(action_name)
            end
        end
        return result
    end
    return { success = false, error = "Unknown action" }
end

--- Gets the action name
--- Converts the action id to the action name
--- @param number action_id The ID of the action
--- @return string The name of the action
function ACTIONS.get_action_name(action_id)
    return ID_TO_ACTION[action_id]
end

--- Gets the action id
--- Converts the action name to the action id
--- @param string action_name The name of the action
--- @return number The ID of the action
function ACTIONS.get_action_id(action_name)
    return ACTION_IDS[action_name]
end

return ACTIONS
