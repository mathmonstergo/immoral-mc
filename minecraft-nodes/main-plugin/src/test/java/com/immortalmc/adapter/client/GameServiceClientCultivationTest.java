package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
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

class GameServiceClientCultivationTest {
    private static final UUID ACCOUNT_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID SESSION_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID OPERATION_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final UUID TECHNIQUE_ID =
            UUID.fromString("44444444-4444-4444-8444-444444444444");

    @Test
    void decodesAuthoritativeMortalCultivationSnapshot() throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation",
                        exchange -> respond(exchange, 200, """
                                {"contract_version":1,"current_level":0,"realm_name":"凡人",
                                 "current_progress":0,"max_exp":50,"realized_total":0,
                                 "unrefined_reserve":20,"reserve_cap":50,"revision":1,
                                 "progress_full":false,"reserve_full":false,"can_advance":false}
                                """)),
                uri -> {
                    CultivationSnapshot snapshot = client(uri)
                            .fetchCultivation(ACCOUNT_ID)
                            .get(2, TimeUnit.SECONDS);

                    assertEquals(0, snapshot.currentLevel());
                    assertEquals("凡人", snapshot.realmName());
                    assertEquals(50L, snapshot.maxExp());
                    assertEquals(0.4, snapshot.reserveRatio());
                });
    }

    @Test
    void decodesAuthoritativeCultivationSnapshot() throws Exception {
        withServer(server -> {
            server.createContext(
                    "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation",
                    exchange -> respond(exchange, 200, cultivationJson()));
            server.createContext(
                    "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation/techniques",
                    exchange -> respond(exchange, 200, """
                            [{"contract_version":1,
                              "life_technique_id":"44444444-4444-4444-8444-444444444444",
                              "technique_id":"wind_split_escape_blade",
                              "display_name":"风裂遁刃诀","definition_version":1,
                              "group_code":"level:22","major_realm":"元婴",
                              "attribute_codes":["wind"],
                              "invested_amount":0,"max_investment":1000,
                              "current_layer":0,"status":"active"}]
                            """));
        },
                uri -> {
                    GameServiceClient client = client(uri);
                    CultivationSnapshot snapshot = client
                            .fetchCultivation(ACCOUNT_ID)
                            .get(2, TimeUnit.SECONDS);
                    List<TechniqueSnapshot> techniques = client
                            .fetchTechniques(ACCOUNT_ID)
                            .get(2, TimeUnit.SECONDS);

                    assertEquals(22, snapshot.currentLevel());
                    assertEquals("元婴后期", snapshot.realmName());
                    assertEquals(0L, snapshot.currentProgress());
                    assertEquals(116_145_360L, snapshot.maxExp());
                    assertEquals(7L, snapshot.revision());
                    assertEquals(0.0, snapshot.currentRatio());
                    assertEquals(0.5, snapshot.reserveRatio());
                    assertEquals(1, techniques.size());
                    assertEquals("风裂遁刃诀", techniques.getFirst().displayName());
                    assertEquals(List.of("wind"), techniques.getFirst().attributeCodes());
                    assertEquals(0, techniques.getFirst().currentLayer());
                });
    }

    @Test
    void techniqueSnapshotsRejectLayersOutsideZeroToThirteen() {
        assertThrows(IllegalArgumentException.class, () -> techniqueAtLayer(-1));
        assertThrows(IllegalArgumentException.class, () -> techniqueAtLayer(14));
    }

    @Test
    void seclusionMutationsRemainAsyncAndCarryIdempotencyKeys() throws Exception {
        AtomicReference<String> startHeader = new AtomicReference<>();
        AtomicReference<JsonNode> startBody = new AtomicReference<>();
        AtomicReference<String> settleHeader = new AtomicReference<>();
        AtomicReference<String> settleBody = new AtomicReference<>();
        withServer(server -> {
            String base = "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation/seclusions";
            server.createContext(base, exchange -> {
                startHeader.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                startBody.set(new ObjectMapper().readTree(exchange.getRequestBody()));
                respond(exchange, 200, seclusionJson("active"));
            });
            server.createContext(base + "/" + SESSION_ID, exchange -> {
                if (exchange.getRequestURI().getPath().endsWith("/settle")) {
                    settleHeader.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                    settleBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                    respond(exchange, 200, seclusionJson("completed"));
                    return;
                }
                respond(exchange, 200, seclusionJson("active"));
            });
        }, uri -> {
            GameServiceClient client = client(uri);
            SeclusionSnapshot started = client
                    .startSeclusion(
                            ACCOUNT_ID,
                            new SeclusionRequest("neutral_training_ground", List.of(TECHNIQUE_ID)),
                            OPERATION_ID)
                    .get(2, TimeUnit.SECONDS);
            SeclusionSnapshot status = client
                    .fetchSeclusion(ACCOUNT_ID, SESSION_ID)
                    .get(2, TimeUnit.SECONDS);
            SeclusionSnapshot settled = client
                    .settleSeclusion(ACCOUNT_ID, SESSION_ID, OPERATION_ID)
                    .get(2, TimeUnit.SECONDS);

            assertEquals(SESSION_ID, started.sessionId());
            assertEquals(Instant.parse("2026-07-16T12:00:10Z"), started.completesAt());
            assertEquals("active", status.status());
            assertEquals("completed", settled.status());
            assertEquals(OPERATION_ID.toString(), startHeader.get());
            assertEquals(OPERATION_ID.toString(), settleHeader.get());
            assertEquals("", settleBody.get());
            assertEquals("neutral_training_ground", startBody.get().get("area_id").textValue());
            assertEquals(TECHNIQUE_ID.toString(), startBody.get().get("technique_ids").get(0).textValue());
        });
    }

    @Test
    void breakthroughAndItemAdjustmentUseAuthoritativeContracts() throws Exception {
        AtomicReference<JsonNode> breakthroughBody = new AtomicReference<>();
        AtomicReference<JsonNode> itemBody = new AtomicReference<>();
        withServer(server -> {
            String breakthroughBase = "/api/v1/players/" + ACCOUNT_ID
                    + "/current-life/cultivation/breakthroughs";
            server.createContext(breakthroughBase, exchange -> {
                breakthroughBody.set(new ObjectMapper().readTree(exchange.getRequestBody()));
                respond(exchange, 200, breakthroughJson("active", "success"));
            });
            server.createContext(breakthroughBase + "/" + SESSION_ID, exchange -> {
                if (exchange.getRequestURI().getPath().endsWith("/settle")) {
                    respond(exchange, 200, breakthroughJson("completed", "success"));
                    return;
                }
                respond(exchange, 200, breakthroughJson("active", "success"));
            });
            server.createContext(
                    "/api/v1/players/" + ACCOUNT_ID + "/current-life/items/adjustments",
                    exchange -> {
                        itemBody.set(new ObjectMapper().readTree(exchange.getRequestBody()));
                        respond(exchange, 200, """
                                {"contract_version":1,"item_code":"foundation_pill",
                                 "delta_quantity":10,"balance_after":10}
                                """);
                    });
        }, uri -> {
            GameServiceClient client = client(uri);
            BreakthroughSnapshot started = client
                    .startBreakthrough(ACCOUNT_ID, new BreakthroughRequest(3), OPERATION_ID)
                    .get(2, TimeUnit.SECONDS);
            BreakthroughSnapshot status = client
                    .fetchBreakthrough(ACCOUNT_ID, SESSION_ID)
                    .get(2, TimeUnit.SECONDS);
            BreakthroughSnapshot settled = client
                    .settleBreakthrough(ACCOUNT_ID, SESSION_ID, OPERATION_ID)
                    .get(2, TimeUnit.SECONDS);
            ItemAdjustmentSnapshot item = client
                    .adjustItem(
                            ACCOUNT_ID,
                            new ItemAdjustmentRequest("foundation_pill", 10),
                            OPERATION_ID)
                    .get(2, TimeUnit.SECONDS);

            assertEquals(3, started.pillCount());
            assertEquals(7_500, status.successBasisPoints());
            assertEquals("success", settled.outcome());
            assertEquals(Instant.parse("2026-07-16T13:10:00Z"), settled.settledAt());
            assertEquals(10L, item.balanceAfter());
            assertEquals(3, breakthroughBody.get().get("pill_count").intValue());
            assertEquals("foundation_pill", itemBody.get().get("item_code").textValue());
        });
    }

    @Test
    void cultivationMutationDecodesStableDomainError() throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation/seclusions",
                        exchange -> respond(exchange, 409, """
                                {"error":{"code":"cultivation.session_active",
                                "message":"A cultivation session is already active.","retryable":false}}
                                """)),
                uri -> {
                    ExecutionException failure = assertThrows(
                            ExecutionException.class,
                            () -> client(uri)
                                    .startSeclusion(
                                            ACCOUNT_ID,
                                            new SeclusionRequest(
                                                    "neutral_training_ground", List.of(TECHNIQUE_ID)),
                                            OPERATION_ID)
                                    .get(2, TimeUnit.SECONDS));
                    GameServiceException error = assertInstanceOf(GameServiceException.class, failure.getCause());
                    assertEquals(409, error.statusCode());
                    assertEquals("cultivation.session_active", error.code());
                    assertTrue(!error.retryable());
                });
    }

    @Test
    void breakthroughAndAdministrativeItemDtosRejectNonAuthoritativeShapes() {
        assertThrows(
                IllegalArgumentException.class,
                () -> new BreakthroughSnapshot(
                        1,
                        SESSION_ID,
                        "active",
                        10,
                        14,
                        1,
                        5_000,
                        1,
                        null,
                        null,
                        Instant.parse("2026-07-16T13:00:00Z"),
                        Instant.parse("2026-07-16T13:10:00Z"),
                        null));
        assertThrows(
                IllegalArgumentException.class,
                () -> new ItemAdjustmentRequest("foundation_pill", -1));
        BreakthroughSnapshot upperRoll = new BreakthroughSnapshot(
                1,
                SESSION_ID,
                "completed",
                13,
                14,
                10,
                10_000,
                10_000,
                10_000,
                "success",
                Instant.parse("2026-07-16T13:00:00Z"),
                Instant.parse("2026-07-16T13:10:00Z"),
                Instant.parse("2026-07-16T13:10:00Z"));
        assertEquals(10_000, upperRoll.primaryRoll());
    }

    private static GameServiceClient client(URI uri) {
        return new GameServiceClient(uri, HttpClient.newHttpClient());
    }

    private static TechniqueSnapshot techniqueAtLayer(int currentLayer) {
        return new TechniqueSnapshot(
                1,
                TECHNIQUE_ID,
                "wind_split_escape_blade",
                "风裂遁刃诀",
                1,
                "level:22",
                "元婴",
                List.of("wind"),
                0,
                1000,
                currentLayer,
                "active");
    }

    private static String cultivationJson() {
        return """
                {"contract_version":1,"current_level":22,"realm_name":"元婴后期",
                 "current_progress":0,"max_exp":116145360,"realized_total":900000,
                 "unrefined_reserve":58072680,"reserve_cap":116145360,"revision":7,
                 "progress_full":false,"reserve_full":false,"can_advance":false}
                """;
    }

    private static String seclusionJson(String status) {
        return """
                {"contract_version":1,"session_id":"22222222-2222-4222-8222-222222222222",
                 "status":"%s","started_at":"2026-07-16T12:00:00Z",
                 "completes_at":"2026-07-16T12:00:10Z","cumulative_generated":120,
                 "cumulative_reserve_consumed":100,"cumulative_retained":100}
                """.formatted(status);
    }

    private static String breakthroughJson(String status, String outcome) {
        String outcomeJson = outcome == null ? "null" : "\"" + outcome + "\"";
        String settledAt = outcome == null ? "null" : "\"2026-07-16T13:10:00Z\"";
        return """
                {"contract_version":1,"session_id":"22222222-2222-4222-8222-222222222222",
                 "status":"%s","source_level":10,"target_level":14,"pill_count":3,
                 "success_basis_points":7500,"primary_roll":7000,"secondary_roll":null,
                 "outcome":%s,"started_at":"2026-07-16T13:00:00Z",
                 "completes_at":"2026-07-16T13:10:00Z","settled_at":%s}
                """.formatted(status, outcomeJson, settledAt);
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
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
