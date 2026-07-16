package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.CombatKillResult;

@FunctionalInterface
public interface CultivationRewardPresenter {
    void present(CombatKillEventRequest request, CombatKillResult result);
}
