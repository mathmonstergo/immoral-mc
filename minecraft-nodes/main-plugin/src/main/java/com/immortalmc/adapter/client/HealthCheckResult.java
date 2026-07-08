package com.immortalmc.adapter.client;

public record HealthCheckResult(String service, String status, String version) {}
