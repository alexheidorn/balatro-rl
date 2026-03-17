--- RLBridge input module
--- Handles direct game input actions like selecting blinds and making plays
--- Provides interface between AI actions and Balatro's internal functions

local I = {}
local utils = require("utils")

--- Start the basic run
--- Automatically starts the run in the main menu
--- @return table Result with success status and optional error message
function I.start_run()
    local _seed = G.run_setup_seed and G.setup_seed or G.forced_seed or nil
    local _challenge = G.challenge_tab or nil
    local _stake = G.forced_stake or G.PROFILES[G.SETTINGS.profile].MEMORY.stake or 1

    G.FUNCS.start_run(nil, {
        stake = _stake,
        seed = _seed,
        challenge = _challenge
    })
    utils.log_input("start_run " .. utils.completed_success_msg)
    return { success = true }
end

--- Select the current blind on deck
--- Automatically selects the next available blind in the blind selection screen
--- @return table Result with success status and optional error message
function I.select_blind()
    local blind_on_deck = G.GAME.blind_on_deck
    local blind_key = G.GAME.round_resets.blind_choices[blind_on_deck]

    -- Replicate select_blind internals without UIBox traversal
    stop_use()
    G.GAME.facing_blind = true

    G.E_MANAGER:add_event(Event({
        trigger = 'immediate',
        func = function()
            ease_round(1)
            inc_career_stat('c_rounds', 1)
            G.GAME.round_resets.blind = G.P_BLINDS[blind_key]
            G.GAME.round_resets.blind_states[blind_on_deck] = 'Current'
            if G.blind_select then
                G.blind_select:remove()
                G.blind_select = nil
            end
            if G.blind_prompt_box then
                G.blind_prompt_box:remove()
                G.blind_prompt_box = nil
            end
            delay(0.2)
            return true
        end
    }))

    G.E_MANAGER:add_event(Event({
        trigger = 'immediate',
        func = function()
            new_round()
            return true
        end
    }))

    utils.log_input("select_blind " .. utils.completed_success_msg)
    return { success = true }
end

function I.skip_blind()
    local blind_on_deck = G.GAME.blind_on_deck
    local skip_to = blind_on_deck == 'Small' and 'Big' 
                    or blind_on_deck == 'Big' and 'Boss' 
                    or 'Boss'

    -- Replicate skip_blind internals without needing UIBox
    stop_use()
    G.GAME.skips = (G.GAME.skips or 0) + 1

    -- Award tag if one exists for this blind
    local tag_key = G.GAME.round_resets.blind_tags 
                    and G.GAME.round_resets.blind_tags[blind_on_deck]
    if tag_key then
        local tag = G.P_TAGS[tag_key]
        if tag then add_tag(tag) end
    end

    -- Update blind states
    G.GAME.round_resets.blind_states[blind_on_deck] = 'Skipped'
    G.GAME.round_resets.blind_states[skip_to] = 'Select'
    G.GAME.blind_on_deck = skip_to

    play_sound('generic1')

    G.E_MANAGER:add_event(Event({
        trigger = 'immediate',
        func = function()
            delay(0.3)
            for i = 1, #G.jokers.cards do
                G.jokers.cards[i]:calculate_joker({skip_blind = true})
            end
            save_run()
            for i = 1, #G.GAME.tags do
                G.GAME.tags[i]:apply_to_run({type = 'immediate'})
            end
            for i = 1, #G.GAME.tags do
                if G.GAME.tags[i]:apply_to_run({type = 'new_blind_choice'}) then break end
            end
            return true
        end
    }))

    utils.log_input("skip_blind " .. utils.completed_success_msg)
    return { success = true }
end

--- Select a hand
--- Selects the cards based on a table of indexes
--- @param card_indices table Array of card indices to select
--- @return table Result with success status and optional error message
function I.select_hand(card_indices)
    if not card_indices or type(card_indices) ~= "table" then
        return { success = false, error = "Invalid card indices parameter" }
    end

    if #card_indices < 1 then
        return { success = false, error = "Must play minimum one card" }
    end
    if #card_indices > 5 then
        return { success = false, error = "Must play maximum 5 cards" }
    end

    -- Validate hand exists and has cards
    if not G.hand or not G.hand.cards or #G.hand.cards == 0 then
        return { success = false, error = "No hand or cards available" }
    end

    -- Validate all card indices are within bounds
    for i = 1, #card_indices do
        local card_index = card_indices[i]
        if not card_index or card_index < 1 or card_index > #G.hand.cards then
            return { success = false, error = "Card index out of bounds: " .. tostring(card_index) }
        end
        if not G.hand.cards[card_index] then
            return { success = false, error = "Card at index " .. card_index .. " does not exist" }
        end
    end

    -- Click the cards
    for i = 1, #card_indices do
        G.hand.cards[card_indices[i]]:click()
    end
    utils.log_input("select_hand " .. utils.completed_success_msg)
    return { success = true }
end

--- Click "Play Hand" button to play a hand that was selected
--- @return table Result with success status and optional error message
function I.play_hand()
    utils.log_input("play_hand " .. utils.completed_success_msg)
    G.FUNCS.play_cards_from_highlighted()
    return { success = true }
end

--- Click "Discard" button to discard a hand that was selected
--- @return table Result with success status and optional error message
function I.discard_hand()
    G.FUNCS.discard_cards_from_highlighted()
    utils.log_input("select_hand " .. utils.completed_success_msg)
    return { success = true }
end


return I
