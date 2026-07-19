package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class GameServiceClientPhysicalItemsStorageTest {
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID OPERATION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID TECHNIQUE_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");

    @Test
    void itemDeliveryEndpointsUseExactMethodsAndDecodePhysicalIdentity() throws Exception {
        AtomicReference<String> confirmationMethod = new AtomicReference<>();
        withServer(server -> {
                    server.createContext(
                            "/api/v1/players/" + ACCOUNT_ID + "/current-life/items/pending-deliveries",
                            exchange -> respond(exchange, 200, itemListJson("pending_delivery", null)));
                    server.createContext(
                            "/api/v1/players/" + ACCOUNT_ID + "/current-life/items/inventory",
                            exchange -> respond(exchange, 200, itemListJson("owned", "inventory")));
                    server.createContext(
                            "/api/v1/players/" + ACCOUNT_ID + "/current-life/items/" + ITEM_ID
                                    + "/delivery-confirmation",
                            exchange -> {
                                confirmationMethod.set(exchange.getRequestMethod());
                                respond(exchange, 200, "{\"contract_version\":1,\"item\":"
                                        + itemJson("owned", "inventory") + "}");
                            });
                },
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());

                    ItemInstancesSnapshot pending = client.fetchPendingItemDeliveries(ACCOUNT_ID)
                            .get(2, TimeUnit.SECONDS);
                    ItemInstancesSnapshot inventory = client.fetchInventoryItems(ACCOUNT_ID)
                            .get(2, TimeUnit.SECONDS);
                    ItemDeliveryConfirmationSnapshot confirmed = client.confirmItemDelivery(ACCOUNT_ID, ITEM_ID)
                            .get(2, TimeUnit.SECONDS);

                    assertEquals(LIFE_ID, pending.lifeId());
                    assertEquals(ITEM_ID, pending.items().getFirst().itemInstanceId());
                    assertNull(pending.items().getFirst().location());
                    assertEquals("inventory", inventory.items().getFirst().location());
                    assertEquals("PUT", confirmationMethod.get());
                    assertEquals(ITEM_ID, confirmed.item().itemInstanceId());
                });
    }

    @Test
    void learnTechniqueCarriesStableIdempotencyKeyAndPhysicalItemId() throws Exception {
        AtomicReference<String> body = new AtomicReference<>();
        AtomicReference<String> idempotencyKey = new AtomicReference<>();
        withServer(server -> server.createContext(
                        "/api/v1/players/" + ACCOUNT_ID + "/current-life/cultivation/techniques/learn",
                        exchange -> {
                            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                            idempotencyKey.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                            respond(exchange, 200, """
                                    {
                                      "contract_version":1,
                                      "operation_id":"%s",
                                      "item_instance_id":"%s",
                                      "life_technique_id":"%s",
                                      "technique_id":"GF_YinqiShu_01",
                                      "display_name":"引气术",
                                      "current_layer":0,
                                      "status":"active"
                                    }
                                    """.formatted(OPERATION_ID, ITEM_ID, TECHNIQUE_ID));
                        }),
                uri -> {
                    LearnTechniqueSnapshot learned = new GameServiceClient(uri, HttpClient.newHttpClient())
                            .learnTechnique(ACCOUNT_ID, ITEM_ID, OPERATION_ID)
                            .get(2, TimeUnit.SECONDS);

                    assertEquals("{\"item_instance_id\":\"" + ITEM_ID + "\"}", body.get());
                    assertEquals(OPERATION_ID.toString(), idempotencyKey.get());
                    assertEquals(0, learned.currentLayer());
                    assertEquals("GF_YinqiShu_01", learned.techniqueId());
                });
    }

    @Test
    void storageEndpointsPreserveAreaPageRevisionAndMoveCoordinates() throws Exception {
        AtomicReference<String> snapshotQuery = new AtomicReference<>();
        AtomicReference<String> moveBody = new AtomicReference<>();
        AtomicReference<String> idempotencyKey = new AtomicReference<>();
        withServer(server -> {
                    server.createContext(
                            "/api/v1/players/" + ACCOUNT_ID + "/current-life/storage/qi-field",
                            exchange -> {
                                snapshotQuery.set(exchange.getRequestURI().getRawQuery());
                                respond(exchange, 200, storageJson(7));
                            });
                    server.createContext(
                            "/api/v1/players/" + ACCOUNT_ID + "/current-life/storage/qi-field/moves",
                            exchange -> {
                                moveBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                                idempotencyKey.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                                respond(exchange, 200, """
                                        {
                                          "contract_version":1,
                                          "operation_id":"%s",
                                          "move_kind":"move",
                                          "item_instance_id":"%s",
                                          "snapshot":%s
                                        }
                                        """.formatted(OPERATION_ID, ITEM_ID, storageJson(8)));
                            });
                },
                uri -> {
                    GameServiceClient client = new GameServiceClient(uri, HttpClient.newHttpClient());
                    StorageSnapshot snapshot = client.fetchStorage(ACCOUNT_ID, "qi-field", 2)
                            .get(2, TimeUnit.SECONDS);
                    StorageMoveSnapshot moved = client.moveStorage(
                                    ACCOUNT_ID,
                                    "qi-field",
                                    StorageMoveRequest.move(ITEM_ID, 7, 2, 3, 4),
                                    OPERATION_ID)
                            .get(2, TimeUnit.SECONDS);

                    assertEquals("page=2", snapshotQuery.get());
                    assertEquals(7, snapshot.revision());
                    assertEquals(3, snapshot.slots().getFirst().slot());
                    assertEquals(
                            "{\"move_kind\":\"move\",\"item_instance_id\":\"" + ITEM_ID
                                    + "\",\"expected_revision\":7,\"source_page\":2,\"source_slot\":3,"
                                    + "\"destination_page\":2,\"destination_slot\":4,\"view_page\":2}",
                            moveBody.get());
                    assertEquals(OPERATION_ID.toString(), idempotencyKey.get());
                    assertEquals(8, moved.snapshot().revision());
                });
    }

    private static String itemListJson(String status, String location) {
        return "{\"contract_version\":1,\"life_id\":\"" + LIFE_ID + "\",\"items\":["
                + itemJson(status, location) + "]}";
    }

    private static String itemJson(String status, String location) {
        String serializedLocation = location == null ? "null" : "\"" + location + "\"";
        return "{\"contract_version\":1,\"item_instance_id\":\"" + ITEM_ID
                + "\",\"item_code\":\"technique_manual_yinqi\",\"definition_version\":1,"
                + "\"technique_id\":\"GF_YinqiShu_01\",\"status\":\"" + status
                + "\",\"location\":" + serializedLocation + "}";
    }

    private static String storageJson(long revision) {
        return "{\"contract_version\":1,\"life_id\":\"" + LIFE_ID
                + "\",\"area_id\":\"qi-field\",\"catalog_revision\":\"sha256:storage\","
                + "\"permission\":\"immortalmc.storage\",\"page\":2,\"page_count\":9,"
                + "\"item_slots_per_page\":45,\"revision\":" + revision
                + ",\"slots\":[{\"slot\":3,\"item\":" + itemJson("owned", "storage") + "}]}";
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
