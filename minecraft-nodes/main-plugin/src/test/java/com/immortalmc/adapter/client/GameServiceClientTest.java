package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;

class GameServiceClientTest {
    @Test
    void checkHealthReturnsGameServiceHealthContract() throws Exception {
        withHealthServer(200, "{\"service\":\"game-service\",\"status\":\"ok\",\"version\":\"0.1.0\"}", serverUri -> {
            GameServiceClient client = new GameServiceClient(serverUri, HttpClient.newHttpClient());

            HealthCheckResult result = client.checkHealth().get(2, TimeUnit.SECONDS);

            assertEquals("game-service", result.service());
            assertEquals("ok", result.status());
            assertEquals("0.1.0", result.version());
        });
    }

    private static void withHealthServer(int statusCode, String body, ThrowingConsumer<URI> test) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/health", exchange -> {
            byte[] responseBody = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(statusCode, responseBody.length);
            exchange.getResponseBody().write(responseBody);
            exchange.close();
        });
        server.start();
        try {
            test.accept(URI.create("http://127.0.0.1:" + server.getAddress().getPort()));
        } finally {
            server.stop(0);
        }
    }

    @FunctionalInterface
    private interface ThrowingConsumer<T> {
        void accept(T value) throws Exception;
    }
}
