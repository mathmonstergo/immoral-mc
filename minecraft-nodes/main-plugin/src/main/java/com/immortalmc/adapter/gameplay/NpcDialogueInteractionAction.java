package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.dialogue.NpcDialogueAudience;
import com.immortalmc.adapter.dialogue.NpcDialoguePresenter;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.Objects;
import java.util.function.Function;
import org.bukkit.entity.Player;

public final class NpcDialogueInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "npc-dialogue";
    public static final String DIALOGUE_ID_KEY = "dialogue-id";

    private final NpcDialogueRegistry dialogueRegistry;
    private final NpcDialoguePresenter presenter;
    private final AdapterLogger logger;
    private final Function<Player, NpcDialogueAudience> audienceFactory;

    public NpcDialogueInteractionAction(
            NpcDialogueRegistry dialogueRegistry,
            NpcDialoguePresenter presenter,
            AdapterLogger logger,
            Function<Player, NpcDialogueAudience> audienceFactory) {
        this.dialogueRegistry = Objects.requireNonNull(dialogueRegistry, "dialogueRegistry");
        this.presenter = Objects.requireNonNull(presenter, "presenter");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.audienceFactory = Objects.requireNonNull(audienceFactory, "audienceFactory");
    }

    @Override
    public void handle(EntityInteractionDefinition definition, BukkitEntityInteractionContext context) {
        Objects.requireNonNull(definition, "definition");
        Objects.requireNonNull(context, "context");

        String dialogueId = definition.metadataValue(DIALOGUE_ID_KEY).orElse(null);
        if (dialogueId == null) {
            logger.warn("npc_dialogue_rejected minecraft_uuid="
                    + context.player().getUniqueId()
                    + " interaction_id="
                    + definition.id()
                    + " reason=dialogue_id_missing");
            return;
        }

        var dialogue = dialogueRegistry.find(dialogueId).orElse(null);
        if (dialogue == null) {
            logger.warn("npc_dialogue_rejected minecraft_uuid="
                    + context.player().getUniqueId()
                    + " interaction_id="
                    + definition.id()
                    + " dialogue_id="
                    + dialogueId
                    + " reason=dialogue_missing");
            return;
        }

        logger.info("npc_dialogue_started minecraft_uuid="
                + context.player().getUniqueId()
                + " interaction_id="
                + definition.id()
                + " dialogue_id="
                + dialogueId);
        presenter.play(dialogue, audienceFactory.apply(context.player()));
    }
}
