package com.immortalmc.adapter.content;

import java.util.List;

public interface SpiritRootDetectorRepository {
    List<EntityBinding> load();

    void save(List<EntityBinding> bindings);
}
