package com.immortalmc.adapter.dialogue;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class YamlNpcDialogueRepositoryTest {
    @TempDir
    Path tempDir;

    @Test
    void loadsOneDialoguePerYamlFile() throws Exception {
        Path dialoguesDir = tempDir.resolve("dialogues");
        Files.createDirectories(dialoguesDir);
        Files.writeString(
                dialoguesDir.resolve("old-man.yml"),
                """
                id: old-man
                title: "初入凡尘"
                speaker: "老村民"
                line-delay-ticks: 30
                sound: "entity.villager.ambient"
                pitch: 1.0
                opening-lines:
                  - "§6§l任务开始"
                  - "§e初入凡尘"
                lines:
                  - "年轻人，你身上有一股未定的气。"
                  - "去村外的灵石旁看看，也许能照出你的根骨。"
                """,
                StandardCharsets.UTF_8);

        Map<String, NpcDialogueDefinition> loaded =
                new YamlNpcDialogueRepository(dialoguesDir.toFile()).loadAll();

        assertEquals(
                new NpcDialogueDefinition(
                        "old-man",
                        "初入凡尘",
                        "老村民",
                        List.of("§6§l任务开始", "§e初入凡尘"),
                        List.of("年轻人，你身上有一股未定的气。", "去村外的灵石旁看看，也许能照出你的根骨。"),
                        30,
                        "entity.villager.ambient",
                        1.0f),
                loaded.get("old-man"));
    }

    @Test
    void missingOptionalFieldsUseMvpDefaults() throws Exception {
        Path dialoguesDir = tempDir.resolve("dialogues");
        Files.createDirectories(dialoguesDir);
        Files.writeString(
                dialoguesDir.resolve("old-man.yml"),
                """
                id: old-man
                title: "初入凡尘"
                speaker: "老村民"
                opening-lines:
                  - "§6§l任务开始"
                lines:
                  - "年轻人，你身上有一股未定的气。"
                """,
                StandardCharsets.UTF_8);

        NpcDialogueDefinition loaded =
                new YamlNpcDialogueRepository(dialoguesDir.toFile()).loadAll().get("old-man");

        assertEquals(30, loaded.lineDelayTicks());
        assertEquals("entity.villager.ambient", loaded.sound());
        assertEquals(1.0f, loaded.pitch());
    }

    @Test
    void malformedOptionalFieldsFailInsteadOfUsingDefaults() throws Exception {
        Path dialoguesDir = tempDir.resolve("dialogues");
        Files.createDirectories(dialoguesDir);
        Files.writeString(
                dialoguesDir.resolve("old-man.yml"),
                """
                id: old-man
                title: "初入凡尘"
                speaker: "老村民"
                line-delay-ticks: soon
                opening-lines:
                  - "§6§l任务开始"
                lines:
                  - "年轻人，你身上有一股未定的气。"
                """,
                StandardCharsets.UTF_8);

        assertThrows(
                IllegalArgumentException.class,
                () -> new YamlNpcDialogueRepository(dialoguesDir.toFile()).loadAll());
    }
}
