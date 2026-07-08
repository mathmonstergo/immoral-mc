package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.client.SpiritRootSnapshot;

public final class SpiritRootCommandMessages {
    public String playerOnly() {
        return "Only players can detect spirit roots.";
    }

    public String profileMissing() {
        return "ImmortalMC profile is not loaded yet. Rejoin or wait for login sync.";
    }

    public String detecting() {
        return "Detecting spirit root...";
    }

    public String success(SpiritRootDetectionResult result) {
        SpiritRootSnapshot root = result.spiritRoot();
        StringBuilder message = new StringBuilder("Spirit root: ")
                .append(root.label())
                .append(" (")
                .append(root.quality())
                .append("), elements=")
                .append(String.join(", ", root.elements()));
        if (root.mutatedElement() != null) {
            message.append(", mutated=").append(root.mutatedElement());
        }
        if (root.variantElement() != null) {
            message.append(", variant=").append(root.variantElement());
        }
        return message.toString();
    }

    public String failure(Throwable error) {
        Throwable cause = unwrap(error);
        return "Spirit root unavailable: " + cause.getMessage();
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
