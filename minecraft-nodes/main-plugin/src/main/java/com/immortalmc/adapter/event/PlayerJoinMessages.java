package com.immortalmc.adapter.event;

public final class PlayerJoinMessages {
    public String loading() {
        return "Loading ImmortalMC profile...";
    }

    public String success() {
        return "ImmortalMC profile loaded.";
    }

    public String failure(Throwable error) {
        Throwable cause = unwrap(error);
        return "ImmortalMC profile unavailable: " + cause.getMessage();
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
