--- RLBridge input module
--- Handles direct game input actions like selecting blinds and making plays
--- Provides interface between AI actions and Balatro's internal functions

local I = {}
local utils = require("utils")

--- Start the basic run
--- Automatically starts the run in the main menu
--- @param seed_choice optional override seed value (string or number)
--- @return table Result with success status and optional error message
function I.start_run(params)
    local _seed = (params and params.seed) or (G.run_setup_seed and G.setup_seed) or G.forced_seed or nil
    local _challenge = G.challenge_tab or nil
    local _stake = G.forced_stake or G.PROFILES[G.SETTINGS.profile].MEMORY.stake or 1

    if _seed then
        G.forced_seed = _seed
        G.SETTINGS.seed = _seed
        G.run_setup_seed = _seed
        G.setup_seed = _seed
    end

    G.FUNCS.start_run(nil, {
        stake = _stake,
        seed = _seed,
        challenge = _challenge
    })
    
    utils.log_input("start_run " .. utils.completed_success_msg)
    return { success = true }
end
---Comment Out when not debugging
function I.force_beat_blind()
    if G.GAME and G.GAME.chips ~= nil then
        G.GAME.chips = 999999999
    end
    utils.log_input("force_beat_blind: set chips to 999999999")
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
        trigger = 'after',
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
        trigger = 'after',
        func = function()
            new_round()
            return true
        end
    }))

    utils.log_input("select_blind " .. utils.completed_success_msg)
    return { success = true }
end

--- Select a hand
--- Selects the cards based on a table of indexes
--- @param card_indices table Array of card indices to select
--- @return table Result with success status and optional error message
function I.select_hand(card_indices, boss_name)
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

    local handsize = #G.hand.cards;

    -- Validate all card indices are within bounds
    for i = 1, #card_indices do
        local card_index = card_indices[i]
        if not card_index or card_index < 1 or card_index > handsize then
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
---Used for buying cards in the shop
function I.buy_card(slot)
    if not slot or type(slot) ~= "number" then
        return { success = false, error = "Invalid slot parameter" }
    end

    if not G.shop_jokers or not G.shop_jokers.cards then
        return { success = false, error = "Shop not available" }
    end

    if slot < 1 or slot > #G.shop_jokers.cards then
        return { success = false, error = "Slot index out of bounds: " .. tostring(slot) }
    end

    local card = G.shop_jokers.cards[slot]
    if not card then
        return { success = false, error = "No card in slot: " .. tostring(slot) }
    end

    if G.GAME.dollars < card.cost then
        return { success = false, error = "Cannot afford card, cost: " .. tostring(card.cost) }
    end
    
    G.FUNCS.buy_from_shop({ config = {ref_table = card } })
    utils.log_input("buy_card slot " .. tostring(slot) .. " " .. utils.completed_success_msg)
    return { success = true }
end

---For selling a joker
function I.sell_joker(slot)
    if not slot or type(slot) ~= "number" then
        return { success = false, error = "Invalid slot parameter" }
    end

    if not G.jokers or not G.jokers.cards then
        return { success = false, error = "No jokers available" }
    end

    if slot < 1 or slot > #G.jokers.cards then
        return { success = false, error = "Joker slot out of bounds: " .. tostring(slot) }
    end

    local card = G.jokers.cards[slot]
    if not card then
        return {success = false, error = "No joker in slot: " .. tostring(slot) }
    end

    card:sell_card()
    utils.log_input("sell_joker slot " .. tostring(slot) .. " " .. utils.completed_success_msg)
    return { success = true}
end

---For rerolling the joker/card options
function I.reroll_shop()
    if not G.GAME then
        return{ success = false, error = "Game not avalible" }
    end

    local reroll_cost = G.GAME.current_round.reroll_cost or 5
    if G.GAME.dollars < reroll_cost then
        return { success = false, error = "Cannot afford reroll, cost: " .. tostring(reroll_cost) }
    end

    G.FUNCS.reroll_shop()
    utils.log_input("reroll_shop " .. utils.completed_success_msg)
    return { success = true }
end

---for skipping the shop
function I.skip_shop()
    G.FUNCS.toggle_shop()
    utils.log_input("skip_shop " .. utils.completed_success_msg)
    return { success = true }
end
---for cashing out
function I.cash_out()
    if not G.GAME then
        return { success = false, error = "Game not available" }
    end

    local ok, err = pcall(function()
        G.FUNCS.cash_out({ config = {} })
    end)

    if not ok then
        utils.log_input("cash_out ERROR: " .. tostring(err))
        return { success = false, error = tostring(err) }
    end

    utils.log_input("cash_out " .. utils.completed_success_msg)
    return { success = true }
end

return I