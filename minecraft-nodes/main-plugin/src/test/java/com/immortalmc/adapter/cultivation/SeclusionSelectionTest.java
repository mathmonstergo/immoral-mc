package com.immortalmc.adapter.cultivation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.TechniqueSnapshot;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SeclusionSelectionTest {
    @Test
    void zeroLayerActiveTechniqueRemainsSelectable() {
        TechniqueSnapshot technique = technique("练气", "active", 0, 10, 0);
        SeclusionSelection selection = new SeclusionSelection(List.of(technique));

        assertTrue(selection.toggle(technique.lifeTechniqueId()));
        assertEquals(List.of(technique.lifeTechniqueId()), selection.confirmedIds());
    }

    @Test
    void submissionIsStableAndIndependentOfClickOrder() {
        TechniqueSnapshot a = technique("筑基", "active", 2, 10);
        TechniqueSnapshot b = technique("筑基", "active", 4, 10);
        SeclusionSelection selection = new SeclusionSelection(List.of(a, b));
        selection.toggle(b.lifeTechniqueId());
        selection.toggle(a.lifeTechniqueId());

        assertEquals(List.of(a.lifeTechniqueId(), b.lifeTechniqueId()).stream().sorted().toList(), selection.confirmedIds());
    }

    @Test
    void rejectsFullAbandonedMixedRealmAndMoreThanFive() {
        TechniqueSnapshot full = technique("筑基", "active", 10, 10);
        TechniqueSnapshot abandoned = technique("筑基", "abandoned", 1, 10);
        assertFalse(new SeclusionSelection(List.of(full)).toggle(full.lifeTechniqueId()));
        assertFalse(new SeclusionSelection(List.of(abandoned)).toggle(abandoned.lifeTechniqueId()));

        TechniqueSnapshot qi = technique("练气", "active", 1, 10);
        TechniqueSnapshot foundation = technique("筑基", "active", 1, 10);
        SeclusionSelection mixed = new SeclusionSelection(List.of(qi, foundation));
        mixed.toggle(qi.lifeTechniqueId());
        assertFalse(mixed.toggle(foundation.lifeTechniqueId()));

        List<TechniqueSnapshot> six = java.util.stream.IntStream.range(0, 6)
                .mapToObj(ignored -> technique("筑基", "active", 1, 10)).toList();
        SeclusionSelection capped = new SeclusionSelection(six);
        six.subList(0, 5).forEach(t -> capped.toggle(t.lifeTechniqueId()));
        assertFalse(capped.toggle(six.get(5).lifeTechniqueId()));
        assertThrows(IllegalStateException.class, () -> new SeclusionSelection(List.of()).confirmedIds());
    }

    @Test
    void rejectsDifferentGroupsWithinTheSameMajorRealm() {
        TechniqueSnapshot first = technique("level:14", "筑基", "active", 1, 10);
        TechniqueSnapshot second = technique("level:15", "筑基", "active", 1, 10);
        SeclusionSelection selection = new SeclusionSelection(List.of(first, second));

        assertTrue(selection.toggle(first.lifeTechniqueId()));
        assertFalse(selection.toggle(second.lifeTechniqueId()));
    }

    @Test
    void rejectsDifferentCapacitiesWithinTheSameGroup() {
        TechniqueSnapshot first = technique("level:14", "筑基", "active", 1, 10);
        TechniqueSnapshot second = technique("level:14", "筑基", "active", 1, 11);
        SeclusionSelection selection = new SeclusionSelection(List.of(first, second));

        assertTrue(selection.toggle(first.lifeTechniqueId()));
        assertFalse(selection.toggle(second.lifeTechniqueId()));
    }

    private static TechniqueSnapshot technique(String realm, String status, long invested, long max) {
        return technique(realm, status, invested, max, 1);
    }

    private static TechniqueSnapshot technique(
            String realm, String status, long invested, long max, int currentLayer) {
        return technique("group", realm, status, invested, max, currentLayer);
    }

    private static TechniqueSnapshot technique(
            String group, String realm, String status, long invested, long max) {
        return technique(group, realm, status, invested, max, 1);
    }

    private static TechniqueSnapshot technique(
            String group, String realm, String status, long invested, long max, int currentLayer) {
        return new TechniqueSnapshot(1, UUID.randomUUID(), "test", "测试功法", 1, group, realm,
                List.of("water"),
                invested, max, currentLayer, status);
    }
}
