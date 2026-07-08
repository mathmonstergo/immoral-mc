package com.immortalmc.adapter.content;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

public final class SpiritRootDetectorRegistry {
    private final SpiritRootDetectorRepository repository;
    private Set<EntityBinding> bindings = Set.of();

    public SpiritRootDetectorRegistry(SpiritRootDetectorRepository repository) {
        this.repository = Objects.requireNonNull(repository, "repository");
    }

    public synchronized int reload() {
        bindings = new LinkedHashSet<>(repository.load());
        return bindings.size();
    }

    public synchronized int saveDetector(EntityBinding binding) {
        Objects.requireNonNull(binding, "binding");
        LinkedHashSet<EntityBinding> updated = new LinkedHashSet<>(bindings);
        updated.add(binding);
        bindings = updated;
        repository.save(List.copyOf(updated));
        return bindings.size();
    }

    public synchronized boolean matches(EntityBinding binding) {
        return bindings.contains(binding);
    }
}
