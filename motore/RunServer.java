import com.sun.net.httpserver.*;
import java.io.*;
import java.lang.reflect.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import javax.xml.transform.stream.StreamSource;

/** Espone il motore CENED+2.0 via HTTP: POST /calcola (datiInput) -> calcolo.xml ; GET /health. */
public class RunServer {
  static Object engine, evaluation;
  static Method execMethod;
  static Class<?> eng;

  public static void main(String[] a) throws Exception {
    int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
    String profilo = System.getenv().getOrDefault("CENED_PROFILE", "lib");
    eng = Class.forName("it.finlombarda.cened2.engine.CenedPlus2Engine");
    System.out.println("[i] Motore CENED " + eng.getMethod("getVersion").invoke(null));
    engine = eng.getMethod("getInstance", String.class).invoke(null, profilo);
    evaluation = eng.getMethod("getEvaluation").invoke(engine);
    execMethod = evaluation.getClass().getMethod("execute", javax.xml.transform.Source.class);
    HttpServer s = HttpServer.create(new InetSocketAddress(port), 0);
    s.createContext("/health", ex -> reply(ex, 200, "OK"));
    s.createContext("/calcola", ex -> {
      try {
        if (!"POST".equals(ex.getRequestMethod())) { reply(ex, 405, "usare POST"); return; }
        byte[] body = ex.getRequestBody().readAllBytes();
        String xml;
        synchronized (RunServer.class) {  // il motore non è garantito thread-safe
          Object out = execMethod.invoke(evaluation, new StreamSource(new ByteArrayInputStream(body)));
          xml = (out instanceof String) ? (String) out
              : new String((byte[]) eng.getMethod("getXmlSerialized").invoke(engine), StandardCharsets.UTF_8);
        }
        ex.getResponseHeaders().add("Content-Type", "application/xml; charset=UTF-8");
        reply(ex, 200, xml);
      } catch (Throwable t) {
        reply(ex, 500, "ERRORE: " + (t.getCause() != null ? t.getCause() : t));
      }
    });
    s.start();
    System.out.println("[OK] in ascolto su :" + port);
  }

  static void reply(HttpExchange ex, int code, String body) throws IOException {
    byte[] b = body.getBytes(StandardCharsets.UTF_8);
    ex.sendResponseHeaders(code, b.length);
    try (OutputStream o = ex.getResponseBody()) { o.write(b); }
  }
}
