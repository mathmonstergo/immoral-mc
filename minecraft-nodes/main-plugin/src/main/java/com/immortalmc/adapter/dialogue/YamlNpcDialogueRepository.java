package com.immortalmc.adapter.dialogue;

import java.io.File;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.bukkit.configuration.file.YamlConfiguration;

public final class YamlNpcDialogueRepository implements NpcDialogueRepository {
    private static final int DEFAULT_LINE_DELAY_TICKS = 30;
    private static final String DEFAULT_SOUND = "entity.villager.ambient";
    private static final double DEFAULT_PITCH = 1.0d;

    private final File dialoguesDirectory;

    public YamlNpcDialogueRepository(File dialoguesDirectory) {
        this.dialoguesDirectory = Objects.requireNonNull(dialoguesDirectory, "dialoguesDirectory");
    }

    @Override
    public Map<String, NpcDialogueDefinition> loadAll() {
        File[] files = dialoguesDirectory.listFiles((directory, name) -> name.endsWith(".yml"));
        if (files == null) {
            return Map.of();
        }

        Map<String, NpcDialogueDefinition> dialogues = new LinkedHashMap<>();
        for (File file : files) {
            NpcDialogueDefinition dialogue = load(file);
            String expectedId = file.getName().substring(0, file.getName().length() - ".yml".length());
            if (!dialogue.id().equals(expectedId)) {
                throw new IllegalArgumentException("Dialogue file "
                        + file.getName()
                        + " declares id "
                        + dialogue.id()
                        + " but expected "
                        + expectedId);
            }
            dialogues.put(dialogue.id(), dialogue);
        }
        return Map.copyOf(dialogues);
    }

    private static NpcDialogueDefinition load(File file) {
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        String id = requiredString(yaml, "id", file);
        String title = requiredString(yaml, "title", file);
        String speaker = requiredString(yaml, "speaker", file);
        List<String> openingLines = requiredStringList(yaml, "opening-lines", file);
        List<String> lines = requiredStringList(yaml, "lines", file);
        int lineDelayTicks = optionalInt(yaml, "line-delay-ticks", DEFAULT_LINE_DELAY_TICKS, file);
        String sound = optionalString(yaml, "sound", DEFAULT_SOUND, file);
        float pitch = (float) optionalDouble(yaml, "pitch", DEFAULT_PITCH, file);

        return new NpcDialogueDefinition(id, title, speaker, openingLines, lines, lineDelayTicks, sound, pitch);
    }

    private static String requiredString(YamlConfiguration yaml, String key, File file) {
        String value = yaml.getString(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " is missing " + key);
        }
        return value;
    }

    private static List<String> requiredStringList(YamlConfiguration yaml, String key, File file) {
        List<String> values = yaml.getStringList(key);
        if (values.isEmpty() || values.stream().anyMatch(String::isBlank)) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " has invalid " + key);
        }
        return List.copyOf(values);
    }

    private static int optionalInt(YamlConfiguration yaml, String key, int fallback, File file) {
        if (!yaml.isSet(key)) {
            return fallback;
        }
        if (!yaml.isInt(key)) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " has invalid " + key);
        }
        return yaml.getInt(key);
    }

    private static String optionalString(YamlConfiguration yaml, String key, String fallback, File file) {
        if (!yaml.isSet(key)) {
            return fallback;
        }
        if (!yaml.isString(key)) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " has invalid " + key);
        }
        String value = yaml.getString(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " has invalid " + key);
        }
        return value;
    }

    private static double optionalDouble(YamlConfiguration yaml, String key, double fallback, File file) {
        if (!yaml.isSet(key)) {
            return fallback;
        }
        if (!yaml.isDouble(key) && !yaml.isInt(key)) {
            throw new IllegalArgumentException("Dialogue file " + file.getName() + " has invalid " + key);
        }
        return yaml.getDouble(key);
    }
}
