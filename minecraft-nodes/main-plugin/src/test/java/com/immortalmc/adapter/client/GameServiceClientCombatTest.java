package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.immortalmc.adapter.combat.CombatAttributionKind;
import com.immortalmc.adapter.combat.CombatSource;
import com.immortalmc.adapter.mythicmobs.MythicMobDeathSnapshot;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class GameServiceClientCombatTest {
    private static final UUID EVENT_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID LIFE_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID KILL_EVENT_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");

    @Test
    void sendsAmountFreeCombatBatchAndDecodesPerEventResult() throws Exception {
        AtomicReference<String> method = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        withServer(server -> server.createContext(
                        "/api/v1/combat/mythicmob-kills/batch",
                        exchange -> {
                            method.set(exchange.getRequestMethod());
                            body.set(new String(
                                    exchange.getRequestBody().readAllBytes(),
                                    StandardCharsets.UTF_8));
                            respond(exchange, 200, """
                                    {"contract_version":1,"results":[{
                                      "event_id":"11111111-1111-4111-8111-111111111111",
                                      "outcome":"accepted",
                                      "kill_event_id":"33333333-3333-4333-8333-333333333333",
                                      "life_id":"22222222-2222-4222-8222-222222222222",
                                      "reward_amount":12,
                                      "unrefined_balance":120
                                    }]}
                                    """);
                        }),
                uri -> {
                    CombatKillEventRequest request = CombatKillEventRequest.fromSnapshot(snapshot());
                    CombatKillBatchResponse response = new GameServiceClient(uri, HttpClient.newHttpClient())
                            .sendCombatKills(List.of(request))
                            .get(2, TimeUnit.SECONDS);

                    JsonNode json = new ObjectMapper().readTree(body.get());
                    assertEquals("POST", method.get());
                    assertEquals(1, json.get("contract_version").intValue());
                    JsonNode event = json.get("events").get(0);
                    assertEquals(EVENT_ID.toString(), event.get("event_id").textValue());
                    assertEquals("12.5", event.get("mob_level").textValue());
                    assertEquals("damage_over_time", event.get("attribution_kind").textValue());
                    assertFalse(event.has("reward_amount"));
                    assertEquals("accepted", response.results().getFirst().outcome());
                    assertEquals(12L, response.results().getFirst().rewardAmount());
                    assertEquals(120L, response.results().getFirst().unrefinedBalance());
                });
    }

    @Test
    void rejectsMissingDuplicateOrReassignedResultIds() throws Exception {
        assertInvalidResponse("""
                {"contract_version":1,"results":[]}
                """);
        assertInvalidResponse("""
                {"contract_version":1,"results":[
                  {"event_id":"11111111-1111-4111-8111-111111111111","outcome":"not_rewardable","kill_event_id":"33333333-3333-4333-8333-333333333333"},
                  {"event_id":"11111111-1111-4111-8111-111111111111","outcome":"duplicate","kill_event_id":"33333333-3333-4333-8333-333333333333"}
                ]}
                """);
        assertInvalidResponse("""
                {"contract_version":1,"results":[{
                  "event_id":"99999999-9999-4999-8999-999999999999",
                  "outcome":"not_rewardable",
                  "kill_event_id":"33333333-3333-4333-8333-333333333333"
                }]}
                """);
    }

    @Test
    void wholeBatchServiceFailureRemainsRetryable() throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/combat/mythicmob-kills/batch",
                        exchange -> respond(exchange, 503, """
                                {"error":{"code":"service.not_ready","message":"Not ready","retryable":true}}
                                """)),
                uri -> {
                    ExecutionException failure = assertThrows(
                            ExecutionException.class,
                            () -> new GameServiceClient(uri, HttpClient.newHttpClient())
                                    .sendCombatKills(List.of(CombatKillEventRequest.fromSnapshot(snapshot())))
                                    .get(2, TimeUnit.SECONDS));
                    GameServiceException error =
                            assertInstanceOf(GameServiceException.class, failure.getCause());
                    assertEquals(503, error.statusCode());
                    assertTrue(error.retryable());
                });
    }

    private static void assertInvalidResponse(String responseJson) throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/combat/mythicmob-kills/batch",
                        exchange -> respond(exchange, 200, responseJson)),
                uri -> {
                    ExecutionException failure = assertThrows(
                            ExecutionException.class,
                            () -> new GameServiceClient(uri, HttpClient.newHttpClient())
                                    .sendCombatKills(List.of(CombatKillEventRequest.fromSnapshot(snapshot())))
                                    .get(2, TimeUnit.SECONDS));
                    assertInstanceOf(GameServiceException.class, failure.getCause());
                });
    }

    private static MythicMobDeathSnapshot snapshot() {
        UUID entityId = UUID.fromString("44444444-4444-4444-8444-444444444444");
        UUID playerId = UUID.fromString("55555555-5555-4555-8555-555555555555");
        UUID castId = UUID.fromString("66666666-6666-4666-8666-666666666666");
        Instant occurredAt = Instant.parse("2026-07-15T12:00:00Z");
        return new MythicMobDeathSnapshot(
                EVENT_ID,
                "main-1",
                entityId,
                "AzureWolf",
                new java.math.BigDecimal("12.5"),
                new CombatSource(
                        playerId,
                        LIFE_ID,
                        "venom_mist",
                        castId,
                        CombatAttributionKind.DAMAGE_OVER_TIME,
                        occurredAt.minusSeconds(1),
                        occurredAt.plusSeconds(60)),
                "minecraft:overworld",
                12.5,
                64.0,
                -8.25,
                occurredAt);
    }

    private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String body)
            throws IOException {
        byte[] response = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, response.length);
        exchange.getResponseBody().write(response);
        exchange.close();
    }

    private static void withServer(ServerConfigurer configurer, ThrowingConsumer<URI> test)
            throws Exception {
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
