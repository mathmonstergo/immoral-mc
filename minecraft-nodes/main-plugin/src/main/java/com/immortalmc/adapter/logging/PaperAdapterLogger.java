package com.immortalmc.adapter.logging;

import java.util.Objects;
import java.util.logging.Level;
import java.util.logging.Logger;

public final class PaperAdapterLogger implements AdapterLogger {
    private final Logger logger;

    public PaperAdapterLogger(Logger logger) {
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @Override
    public void debug(String message) {
        logger.fine(message);
    }

    @Override
    public void info(String message) {
        logger.info(message);
    }

    @Override
    public void warn(String message) {
        logger.warning(message);
    }

    @Override
    public void warn(String message, Throwable error) {
        logger.log(Level.WARNING, message, error);
    }

    @Override
    public void error(String message, Throwable error) {
        logger.log(Level.SEVERE, message, error);
    }
}
