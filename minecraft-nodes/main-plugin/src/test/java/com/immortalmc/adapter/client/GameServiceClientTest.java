package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
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

    @Test
    void loginPlayerPostsMinecraftIdentityAndReturnsAccountSnapshot() throws Exception {
        AtomicReference<String> method = new AtomicReference<>();
        AtomicReference<String> requestBody = new AtomicReference<>();
        AtomicReference<String> connectionHeader = new AtomicReference<>();
        AtomicReference<String> upgradeHeader = new AtomicReference<>();
        AtomicReference<String> http2SettingsHeader = new AtomicReference<>();
        withServer(server -> {
            server.createContext("/api/v1/players/login", exchange -> {
                method.set(exchange.getRequestMethod());
                connectionHeader.set(exchange.getRequestHeaders().getFirst("Connection"));
                upgradeHeader.set(exchange.getRequestHeaders().getFirst("Upgrade"));
                http2SettingsHeader.set(exchange.getRequestHeaders().getFirst("HTTP2-Settings"));
                requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                byte[] responseBody = """
                        {
                          "account": {
                            "account_id": "10000000-0000-0000-0000-000000000001",
                            "minecraft_uuid": "00000000-0000-0000-0000-000000000010",
                            "player_name": "Sensen"
                          },
                          "current_life": {
                            "life_id": "20000000-0000-0000-0000-000000000001",
                            "account_id": "10000000-0000-0000-0000-000000000001",
                            "generation_no": 1,
                            "status": "alive",
                            "spirit_root": null
                          }
                        }
                        """
                        .getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, responseBody.length);
                exchange.getResponseBody().write(responseBody);
                exchange.close();
            });
        }, serverUri -> {
            GameServiceClient client = new GameServiceClient(serverUri, HttpClient.newHttpClient());

            PlayerLoginResult result = client.loginPlayer(
                            UUID.fromString("00000000-0000-0000-0000-000000000010"), "Sensen")
                    .get(2, TimeUnit.SECONDS);

            assertEquals("POST", method.get());
            assertEquals(
                    "{\"minecraft_uuid\":\"00000000-0000-0000-0000-000000000010\",\"player_name\":\"Sensen\"}",
                    requestBody.get());
            assertNull(connectionHeader.get());
            assertNull(upgradeHeader.get());
            assertNull(http2SettingsHeader.get());
            assertEquals(UUID.fromString("10000000-0000-0000-0000-000000000001"), result.account().accountId());
            assertEquals(UUID.fromString("00000000-0000-0000-0000-000000000010"), result.account().minecraftUuid());
            assertEquals("Sensen", result.account().playerName());
            assertEquals(UUID.fromString("20000000-0000-0000-0000-000000000001"), result.currentLife().lifeId());
            assertEquals(1, result.currentLife().generationNo());
            assertEquals("alive", result.currentLife().status());
        });
    }

    @Test
    void detectSpiritRootPostsAccountScopedRequestAndReturnsDetectionResult() throws Exception {
        AtomicReference<String> method = new AtomicReference<>();
        withServer(server -> {
            server.createContext(
                    "/api/v1/players/10000000-0000-0000-0000-000000000001/current-life/spirit-root",
                    exchange -> {
                        method.set(exchange.getRequestMethod());
                        byte[] responseBody = """
                                {
                                  "life_id": "20000000-0000-0000-0000-000000000001",
                                  "spirit_root": {
                                    "quality": "dual",
                                    "label": "Dual Root",
                                    "elements": ["fire", "water"],
                                    "mutated_element": null,
                                    "variant_element": null
                                  },
                                  "already_detected": false
                                }
                                """
                                .getBytes(StandardCharsets.UTF_8);
                        exchange.getResponseHeaders().add("Content-Type", "application/json");
                        exchange.sendResponseHeaders(200, responseBody.length);
                        exchange.getResponseBody().write(responseBody);
                        exchange.close();
                    });
        }, serverUri -> {
            GameServiceClient client = new GameServiceClient(serverUri, HttpClient.newHttpClient());

            SpiritRootDetectionResult result = client.detectSpiritRoot(
                            UUID.fromString("10000000-0000-0000-0000-000000000001"))
                    .get(2, TimeUnit.SECONDS);

            assertEquals("POST", method.get());
            assertEquals(UUID.fromString("20000000-0000-0000-0000-000000000001"), result.lifeId());
            assertEquals("dual", result.spiritRoot().quality());
            assertEquals("Dual Root", result.spiritRoot().label());
            assertEquals(List.of("fire", "water"), result.spiritRoot().elements());
            assertEquals(false, result.alreadyDetected());
        });
    }

    private static void withHealthServer(int statusCode, String body, ThrowingConsumer<URI> test) throws Exception {
        withServer(server -> {
            server.createContext("/health", exchange -> {
                byte[] responseBody = body.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().add("Content-Type", "application/json");
                exchange.sendResponseHeaders(statusCode, responseBody.length);
                exchange.getResponseBody().write(responseBody);
                exchange.close();
            });
        }, test);
    }

    private static void withServer(ServerConfigurer configurer, ThrowingConsumer<URI> test) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        configurer.configure(server);
        server.start();
        try {
            test.accept(URI.create("http://127.0.0.1:" + server.getAddress().getPort()));
        } finally {
            server.stop(0);
        }
    }

    @FunctionalInterface
    private interface ServerConfigurer {
        void configure(HttpServer server) throws IOException;
    }

    @FunctionalInterface
    private interface ThrowingConsumer<T> {
        void accept(T value) throws Exception;
    }
}
