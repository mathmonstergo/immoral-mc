package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class GameServiceClientQuestTest {
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID OPERATION_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");

    @Test
    void fetchQuestInteractionStatePostsProviderListAndDecodesCompleteSnakeCaseProjection() throws Exception {
        AtomicReference<String> method = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/quest-interaction-state",
                        exchange -> {
                            method.set(exchange.getRequestMethod());
                            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                            respond(exchange, 200, interactionJson("ready_to_turn_in", 1, true));
                        }),
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());

                    QuestInteractionState result = client.fetchQuestInteractionState(
                                    ACCOUNT_ID, List.of("old-man", "village-chief"))
                            .get(2, TimeUnit.SECONDS);

                    assertEquals("POST", method.get());
                    assertEquals("{\"provider_ids\":[\"old-man\",\"village-chief\"]}", body.get());
                    assertEquals(1, result.contractVersion());
                    assertEquals(ACCOUNT_ID, result.accountId());
                    assertEquals(LIFE_ID, result.lifeId());
                    assertEquals(2, result.revision().player());
                    assertEquals(3, result.revision().quest());
                    assertEquals("sha256:definitions", result.revision().definitions());
                    assertEquals(2000, result.cacheTtlMs());
                    assertEquals("first-steps:ready_to_turn_in", result.providers().getFirst().stateKey());
                    assertEquals("first-steps", result.providers().getFirst().directActionQuestId());
                    assertEquals("老村民", result.providers().getFirst().proximityBark().speaker());
                    assertEquals("看来你已经有所收获。", result.providers().getFirst().proximityBark().text());
                    assertEquals("ready_to_turn_in", result.providers().getFirst().quests().getFirst().state());
                    assertEquals("first-steps.ready", result.providers().getFirst().quests().getFirst().dialogueKey());
                    assertEquals(1, result.trackedQuest().objectives().getFirst().current());
                    assertEquals("返回老村民处", result.trackedQuest().nextActionHint());
                });
    }

    @Test
    void acceptQuestUsesExactPutContractAndReturnsMutationProjection() throws Exception {
        assertMutationContract("accept");
    }

    @Test
    void turnInQuestUsesExactPutContractAndReturnsMutationProjection() throws Exception {
        assertMutationContract("turn-in");
    }

    @Test
    void domainErrorEnvelopeBecomesNonRetryableGameServiceException() throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/quests/first-steps/accept",
                        exchange -> respond(exchange, 409, """
                                {"error":{"code":"quest.not_ready","message":"Quest objectives are not complete.","retryable":false}}
                                """)),
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());

                    ExecutionException failure = assertThrows(
                            ExecutionException.class,
                            () -> client.acceptQuest(ACCOUNT_ID, "first-steps", "old-man", OPERATION_ID)
                                    .get(2, TimeUnit.SECONDS));
                    GameServiceException error = assertInstanceOf(GameServiceException.class, failure.getCause());

                    assertEquals(409, error.statusCode());
                    assertEquals("quest.not_ready", error.code());
                    assertEquals("Quest objectives are not complete.", error.getMessage());
                    assertFalse(error.retryable());
                });
    }

    @Test
    void questRequestsRetainTwoSecondTimeout() throws Exception {
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/quest-interaction-state",
                        exchange -> {
                            try {
                                Thread.sleep(Duration.ofSeconds(3).toMillis());
                                respond(exchange, 200, interactionJson("available", 0, false));
                            } catch (InterruptedException ignored) {
                                Thread.currentThread().interrupt();
                            }
                        }),
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());
                    long startedAt = System.nanoTime();

                    ExecutionException failure = assertThrows(
                            ExecutionException.class,
                            () -> client.fetchQuestInteractionState(ACCOUNT_ID, List.of("old-man"))
                                    .get(4, TimeUnit.SECONDS));

                    assertInstanceOf(HttpTimeoutException.class, failure.getCause());
                    assertTrue(Duration.ofNanos(System.nanoTime() - startedAt).compareTo(Duration.ofSeconds(3)) < 0);
                });
    }

    private static void assertMutationContract(String operation) throws Exception {
        AtomicReference<String> method = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        AtomicReference<String> idempotencyKey = new AtomicReference<>();
        String path = "/api/v1/players/" + ACCOUNT_ID + "/current-life/quests/first-steps/" + operation;
        withServer(server -> server.createContext(path, exchange -> {
                    method.set(exchange.getRequestMethod());
                    body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                    idempotencyKey.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                    respond(exchange, 200, mutationJson(operation.equals("accept") ? "active" : "completed"));
                }),
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());

                    QuestMutationResult result = operation.equals("accept")
                            ? client.acceptQuest(ACCOUNT_ID, "first-steps", "old-man", OPERATION_ID)
                                    .get(2, TimeUnit.SECONDS)
                            : client.turnInQuest(ACCOUNT_ID, "first-steps", "old-man", OPERATION_ID)
                                    .get(2, TimeUnit.SECONDS);

                    assertEquals("PUT", method.get());
                    assertEquals("{\"provider_id\":\"old-man\"}", body.get());
                    assertEquals(OPERATION_ID.toString(), idempotencyKey.get());
                    assertEquals(OPERATION_ID, result.operationId());
                    assertTrue(result.changed());
                    assertEquals(operation.equals("accept") ? "active" : "completed", result.quest().state());
                    assertEquals(ACCOUNT_ID, result.interactionState().accountId());
                    assertEquals("first-steps", result.interactionState().providers().getFirst().quests().getFirst().questId());
                });
    }

    private static String mutationJson(String state) {
        return """
                {
                  "operation_id":"%s",
                  "changed":true,
                  "quest":%s,
                  "interaction_state":%s
                }
                """.formatted(OPERATION_ID, questJson(state, state.equals("completed") ? 1 : 0),
                interactionJson(state, state.equals("completed") ? 1 : 0, state.equals("completed")));
    }

    private static String interactionJson(String state, int current, boolean completed) {
        String tracked = state.equals("active") || state.equals("ready_to_turn_in")
                ? """
                  {"quest_id":"first-steps","title":"初入凡尘","state":"%s","objectives":[%s],"next_action_hint":"%s"}
                  """.formatted(state, objectiveJson(current, completed), current == 0 ? "前往鉴灵师处" : "返回老村民处")
                : "null";
        String bark = state.equals("ready_to_turn_in")
                ? "{\"key\":\"first-steps:ready_to_turn_in\",\"speaker\":\"老村民\",\"text\":\"看来你已经有所收获。\",\"cooldown_seconds\":60}"
                : "null";
        return """
                {
                  "contract_version":1,
                  "account_id":"%s",
                  "life_id":"%s",
                  "revision":{"player":2,"quest":3,"definitions":"sha256:definitions"},
                  "providers":[{
                    "provider_id":"old-man",
                    "state_key":"first-steps:%s",
                    "quests":[%s],
                    "actionable_quest_ids":["first-steps"],
                    "direct_action_quest_id":"first-steps",
                    "proximity_bark":%s
                  }],
                  "tracked_quest":%s,
                  "cache_ttl_ms":2000
                }
                """.formatted(ACCOUNT_ID, LIFE_ID, state, questJson(state, current), bark, tracked);
    }

    private static String questJson(String state, int current) {
        String action = switch (state) {
            case "available" -> "offer";
            case "active" -> "remind";
            case "ready_to_turn_in" -> "turn_in";
            default -> "talk";
        };
        String dialogue = state.equals("ready_to_turn_in") ? "first-steps.ready" : "first-steps." + state;
        return """
                {"quest_id":"first-steps","title":"初入凡尘","category":"main","state":"%s","action":"%s",\
                "dialogue_key":"%s","objectives":[%s]}
                """.formatted(state, action, dialogue, objectiveJson(current, current == 1));
    }

    private static String objectiveJson(int current, boolean completed) {
        return """
                {"objective_id":"detect-spirit-root","title":"灵根检测","current":%d,"required":1,"completed":%s}
                """.formatted(current, completed);
    }

    private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String body)
            throws IOException {
        byte[] response = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, response.length);
        exchange.getResponseBody().write(response);
        exchange.close();
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
