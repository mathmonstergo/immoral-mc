package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.HealthCheckResult;

public final class HealthCommandMessages {
    public String checking() {
        return "Checking Game Service health...";
    }

    public String success(HealthCheckResult result) {
        return "Game Service: " + result.service() + " " + result.status() + " (" + result.version() + ")";
    }

    public String failure(Throwable error) {
        Throwable cause = unwrap(error);
        return "Game Service unavailable: " + cause.getMessage();
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }

    public String usage() {
        return "Usage: /immortal <health|spirit-root|spirit-root-detector|npc-dialogue|quest>";
    }
}
