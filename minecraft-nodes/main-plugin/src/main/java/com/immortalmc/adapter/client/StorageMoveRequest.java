package com.immortalmc.adapter.client;

import java.util.UUID;

public record StorageMoveRequest(
        String moveKind,
        UUID itemInstanceId,
        long expectedRevision,
        Integer sourcePage,
        Integer sourceSlot,
        Integer destinationPage,
        Integer destinationSlot,
        int viewPage) {
    public StorageMoveRequest {
        if (moveKind == null || itemInstanceId == null || expectedRevision < 0 || viewPage < 1) {
            throw new IllegalArgumentException("Storage move identity and revision are required");
        }
        boolean source = sourcePage != null && sourceSlot != null;
        boolean destination = destinationPage != null && destinationSlot != null;
        if (sourcePage != null ^ sourceSlot != null || destinationPage != null ^ destinationSlot != null) {
            throw new IllegalArgumentException("Storage move coordinates must be complete");
        }
        validateCoordinate(sourcePage, sourceSlot, "source");
        validateCoordinate(destinationPage, destinationSlot, "destination");
        switch (moveKind) {
            case "deposit" -> {
                if (source || !destination) {
                    throw new IllegalArgumentException("Deposit requires only destination storage coordinates");
                }
            }
            case "withdraw" -> {
                if (!source || destination) {
                    throw new IllegalArgumentException("Withdraw requires only source storage coordinates");
                }
            }
            case "move" -> {
                if (!source || !destination || sourcePage.equals(destinationPage) && sourceSlot.equals(destinationSlot)) {
                    throw new IllegalArgumentException("Move requires distinct source and destination coordinates");
                }
            }
            default -> throw new IllegalArgumentException("Unknown storage move kind: " + moveKind);
        }
    }

    public static StorageMoveRequest deposit(UUID itemInstanceId, long revision, int page, int slot) {
        return new StorageMoveRequest("deposit", itemInstanceId, revision, null, null, page, slot, page);
    }

    public static StorageMoveRequest withdraw(UUID itemInstanceId, long revision, int page, int slot) {
        return new StorageMoveRequest("withdraw", itemInstanceId, revision, page, slot, null, null, page);
    }

    public static StorageMoveRequest move(UUID itemInstanceId, long revision, int page, int fromSlot, int toSlot) {
        return new StorageMoveRequest("move", itemInstanceId, revision, page, fromSlot, page, toSlot, page);
    }

    private static void validateCoordinate(Integer page, Integer slot, String name) {
        if (page == null) {
            return;
        }
        if (page < 1 || slot < 0 || slot >= 45) {
            throw new IllegalArgumentException(name + " storage coordinate is outside supported bounds");
        }
    }
}
