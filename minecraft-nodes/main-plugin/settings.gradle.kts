pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        exclusiveContent {
            forRepository {
                maven("https://repo.papermc.io/repository/maven-public/")
            }
            filter {
                includeGroup("io.papermc.paper")
                includeGroup("com.mojang")
                includeGroup("net.md-5")
            }
        }
        exclusiveContent {
            forRepository {
                maven("https://maven.citizensnpcs.co/repo")
            }
            filter {
                includeGroup("net.citizensnpcs")
            }
        }
        exclusiveContent {
            forRepository {
                maven("https://mvn.lumine.io/repository/maven-public/")
            }
            filter {
                includeGroup("io.lumine")
            }
        }
    }
}

rootProject.name = "immortal-main-plugin"
