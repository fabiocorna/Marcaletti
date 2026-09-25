# Servizio HTTP attorno al motore CENED+2.0 (POST /calcola: datiInput.xml -> calcolo.xml).
# Il jar del motore NON è nel repository: copiarlo dalla propria installazione CENED+2.0 in
# motore/engine/ (es. cened2-lib-1.1.15-full.jar). Vedi docs/DEPLOY_VPS.md.
FROM eclipse-temurin:11-jdk
WORKDIR /motore
COPY engine/ ./engine/
COPY RunServer.java .
RUN javac -cp "engine/*" RunServer.java
EXPOSE 8080
CMD ["java", "-Xmx1g", "-cp", "engine/*:.", "RunServer"]
