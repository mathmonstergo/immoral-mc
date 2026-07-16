package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.TechniqueSnapshot;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public final class SeclusionSelection {
    private final Map<UUID, TechniqueSnapshot> techniques = new HashMap<>();
    private final Set<UUID> selected = new HashSet<>();

    public SeclusionSelection(List<TechniqueSnapshot> techniques) {
        for (TechniqueSnapshot technique : techniques) {
            this.techniques.put(technique.lifeTechniqueId(), technique);
        }
    }

    public boolean toggle(UUID id) {
        if (selected.remove(id)) {
            return true;
        }
        TechniqueSnapshot technique = techniques.get(id);
        if (technique == null || selected.size() == 5 || !"active".equals(technique.status())
                || technique.investedAmount() >= technique.maxInvestment()) {
            return false;
        }
        if (!selected.isEmpty()) {
            TechniqueSnapshot first = techniques.get(selected.iterator().next());
            if (!first.majorRealm().equals(technique.majorRealm())) {
                return false;
            }
        }
        selected.add(id);
        return true;
    }

    public boolean selected(UUID id) {
        return selected.contains(id);
    }

    public List<UUID> confirmedIds() {
        if (selected.isEmpty()) {
            throw new IllegalStateException("Select at least one technique");
        }
        return selected.stream().sorted().toList();
    }
}
