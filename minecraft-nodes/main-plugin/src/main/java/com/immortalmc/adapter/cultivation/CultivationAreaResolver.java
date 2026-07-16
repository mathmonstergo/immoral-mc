package com.immortalmc.adapter.cultivation;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.bukkit.configuration.ConfigurationSection;

public final class CultivationAreaResolver {
    private final List<Area> areas;

    private CultivationAreaResolver(List<Area> areas) {
        this.areas = List.copyOf(areas);
    }

    public static CultivationAreaResolver from(ConfigurationSection config) {
        List<Area> areas = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        for (var value : config.getMapList("cultivation.areas")) {
            String id = text(value.get("area-id"), "area-id");
            String world = text(value.get("world"), "world");
            if (!ids.add(id)) {
                throw new IllegalArgumentException("Duplicate cultivation area-id: " + id);
            }
            Point min = point(value.get("min"), "min");
            Point max = point(value.get("max"), "max");
            Area area = new Area(id, world, min, max);
            if (areas.stream().anyMatch(existing -> existing.overlaps(area))) {
                throw new IllegalArgumentException("Cultivation areas overlap in world " + world);
            }
            areas.add(area);
        }
        return new CultivationAreaResolver(areas);
    }

    public Optional<String> resolve(String world, double x, double y, double z) {
        return areas.stream()
                .filter(area -> area.contains(world, x, y, z))
                .map(Area::id)
                .findFirst();
    }

    private static String text(Object value, String field) {
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return text;
    }

    private static Point point(Object value, String field) {
        if (!(value instanceof java.util.Map<?, ?> map)) {
            throw new IllegalArgumentException(field + " must be a coordinate map");
        }
        return new Point(
                number(map.get("x"), field + ".x"),
                number(map.get("y"), field + ".y"),
                number(map.get("z"), field + ".z"));
    }

    private static double number(Object value, String field) {
        if (!(value instanceof Number number) || !Double.isFinite(number.doubleValue())) {
            throw new IllegalArgumentException(field + " must be finite");
        }
        return number.doubleValue();
    }

    private record Point(double x, double y, double z) {}

    private record Area(String id, String world, Point min, Point max) {
        private Area {
            if (min.x > max.x || min.y > max.y || min.z > max.z) {
                throw new IllegalArgumentException("Cultivation area minimum exceeds maximum");
            }
        }

        boolean contains(String candidateWorld, double x, double y, double z) {
            return world.equals(candidateWorld)
                    && x >= min.x
                    && x <= max.x
                    && y >= min.y
                    && y <= max.y
                    && z >= min.z && z <= max.z;
        }

        boolean overlaps(Area other) {
            return world.equals(other.world)
                    && min.x <= other.max.x
                    && max.x >= other.min.x
                    && min.y <= other.max.y
                    && max.y >= other.min.y
                    && min.z <= other.max.z && max.z >= other.min.z;
        }
    }
}
