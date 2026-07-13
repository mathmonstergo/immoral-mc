package com.immortalmc.adapter.client;

public final class GameServiceException extends RuntimeException {
    private final int statusCode;
    private final String code;
    private final boolean retryable;

    public GameServiceException(String message) {
        this(-1, "game_service.error", message, true, null);
    }

    public GameServiceException(String message, Throwable cause) {
        this(-1, "game_service.error", message, true, cause);
    }

    public GameServiceException(int statusCode, String code, String message, boolean retryable) {
        this(statusCode, code, message, retryable, null);
    }

    private GameServiceException(int statusCode, String code, String message, boolean retryable, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
        this.code = code;
        this.retryable = retryable;
    }

    public int statusCode() {
        return statusCode;
    }

    public String code() {
        return code;
    }

    public boolean retryable() {
        return retryable;
    }
}
