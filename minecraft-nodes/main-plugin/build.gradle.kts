plugins {
    java
}

group = "com.immortalmc"
version = "0.1.0-SNAPSHOT"

java {
    toolchain.languageVersion.set(JavaLanguageVersion.of(21))
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT")
    compileOnly("net.citizensnpcs:citizens-main:2.0.43-SNAPSHOT") {
        isTransitive = false
    }
    compileOnly("io.lumine:Mythic-Dist:5.12.1") {
        isTransitive = false
    }
    compileOnly("org.xerial:sqlite-jdbc:3.53.2.0")

    implementation("com.fasterxml.jackson.core:jackson-databind:2.18.2")
    implementation("com.fasterxml.jackson.datatype:jackson-datatype-jsr310:2.18.2")

    testImplementation("io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT")
    testImplementation("io.lumine:Mythic-Dist:5.12.1") {
        isTransitive = false
    }
    testImplementation("org.xerial:sqlite-jdbc:3.53.2.0")
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    testImplementation("org.mockito:mockito-core:5.15.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher:1.11.4")
}

tasks.test {
    useJUnitPlatform()
}
