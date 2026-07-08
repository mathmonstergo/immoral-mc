package com.immortalmc.adapter.testsupport;

import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.ArrayList;
import java.util.List;

public final class RecordingAdapterLogger implements AdapterLogger {
    private final List<Entry> entries = new ArrayList<>();

    @Override
    public void debug(String message) {
        entries.add(new Entry("debug", message, null));
    }

    @Override
    public void info(String message) {
        entries.add(new Entry("info", message, null));
    }

    @Override
    public void warn(String message) {
        entries.add(new Entry("warn", message, null));
    }

    @Override
    public void warn(String message, Throwable error) {
        entries.add(new Entry("warn", message, error));
    }

    @Override
    public void error(String message, Throwable error) {
        entries.add(new Entry("error", message, error));
    }

    public List<Entry> entries() {
        return List.copyOf(entries);
    }

    public List<String> messagesAt(String level) {
        return entries.stream()
                .filter(entry -> entry.level().equals(level))
                .map(Entry::message)
                .toList();
    }

    public record Entry(String level, String message, Throwable error) {}
}
