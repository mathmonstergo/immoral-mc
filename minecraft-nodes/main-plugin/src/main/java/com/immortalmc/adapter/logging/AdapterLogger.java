package com.immortalmc.adapter.logging;

public interface AdapterLogger {
    void debug(String message);

    void info(String message);

    void warn(String message);

    void warn(String message, Throwable error);

    void error(String message, Throwable error);
}
