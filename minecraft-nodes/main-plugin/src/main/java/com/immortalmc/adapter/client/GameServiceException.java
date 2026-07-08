package com.immortalmc.adapter.client;

public final class GameServiceException extends RuntimeException {
    public GameServiceException(String message) {
        super(message);
    }

    public GameServiceException(String message, Throwable cause) {
        super(message, cause);
    }
}
