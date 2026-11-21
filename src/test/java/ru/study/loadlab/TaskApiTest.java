package ru.study.loadlab;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class TaskApiTest {
    @Autowired TestRestTemplate http;
    @Test void lifecyclePersistsChangesAndDeletes() {
        var created = http.postForEntity("/api/tasks", Map.of("title", "Lifecycle test", "priority", 3), JsonNode.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        String path = created.getHeaders().getLocation().getPath();
        assertThat(created.getBody().get("status").asText()).isEqualTo("OPEN");
        var changed = http.exchange(path, HttpMethod.PUT,
                new HttpEntity<>(Map.of("title", "Updated test", "priority", 5, "status", "DONE")), JsonNode.class);
        assertThat(changed.getStatusCode()).isEqualTo(HttpStatus.OK);
        var read = http.getForObject(path, JsonNode.class);
        assertThat(read.get("title").asText()).isEqualTo("Updated test");
        assertThat(read.get("priority").asInt()).isEqualTo(5);
        assertThat(read.get("status").asText()).isEqualTo("DONE");
        assertThat(http.exchange(path, HttpMethod.DELETE, HttpEntity.EMPTY, Void.class).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(http.getForEntity(path, JsonNode.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
    @Test void filtersAndPaginationUseRealSeedData() {
        var response = http.getForEntity("/api/tasks?status=OPEN&minPriority=3&q=study&limit=5&offset=0", JsonNode.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        var items = response.getBody().get("items");
        assertThat(items.size()).isEqualTo(5);
        for (var item : items) {
            assertThat(item.get("title").asText()).contains("study");
            assertThat(item.get("priority").asInt()).isGreaterThanOrEqualTo(3);
            assertThat(item.get("status").asText()).isEqualTo("OPEN");
        }
        var next = http.getForObject("/api/tasks?status=OPEN&minPriority=3&q=study&limit=5&offset=5", JsonNode.class);
        assertThat(next.get("items").get(0).get("id").asLong()).isGreaterThan(items.get(4).get("id").asLong());
    }
    @Test void rejectsInvalidPayloadAndSearch() {
        assertThat(http.postForEntity("/api/tasks", Map.of("title", "", "priority", 7), JsonNode.class).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(http.getForEntity("/api/tasks?limit=999", JsonNode.class).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
    @Test void missingUpdatesDoNotCreateRecords() {
        assertThat(http.exchange("/api/tasks/999999", HttpMethod.PUT,
                new HttpEntity<>(Map.of("title", "Missing", "priority", 1, "status", "OPEN")), JsonNode.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
    }
}
