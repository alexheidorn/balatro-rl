from stable_baselines3.common.callbacks import CheckpointCallback

class WinTracker(BaseCallback):
    def __init__(self, log_freq=10, verbose=1):
        super().__init__(verbose)
        self.log_freq = log_freq

        self.total_episodes = 0
        self.total_wins = 0
        self.best_ante = 0
        self.best_round = 0
        self.chips = 0
        self.jokers = []

    def _win_pct(self):
        if self.total_episodes == 0:
            return 0.0
        return round(100.0 * self.total_wins / self.total_episodes, 2)
    
    def _on_step(self) -> bool:
        dones = self.locals.get("dones", [])
        infos = self.locals.get("infos", [])

        for done, info in zip(dones, infos):
            if not done:
                continue

            self.total_episodes += 1

            won = bool(info.get("won", False))
            if won:
                self.total_wins += 1
            
            ante = info.get("ante", 0)
            round_ = info.get("round", 0)
            self.chips = info.get("chips", 0)
            self.jokers = len(info.get("jokers", []))


            if ante > self.best_ante or (ante == self.best_ante and round_ > self.best_round):
                self.best_ante = ante
                self.best_round = round_
            
            self.logger.record("custom/win_pct",    self._win_pct())
            self.logger.record("custom/best_ante",  self.best_ante)
            self.logger.record("custom/best_round", self.best_round)
            self.logger.record("custom/chips", self.chips)
            self.logger.record("custom/jokers", self.jokers)
            self.logger.record("custom/total_wins", self.total_wins)

        return True