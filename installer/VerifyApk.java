import com.android.apksig.ApkVerifier;
import com.android.apksig.SigningCertificateLineage;
import java.io.File;
import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.LinkedHashSet;
import java.util.Set;

/** Verify the actual APK and its authenticated key-rotation lineage using apksig. */
public final class VerifyApk {
    private static String digest(X509Certificate cert) throws Exception {
        byte[] value = MessageDigest.getInstance("SHA-256").digest(cert.getEncoded());
        StringBuilder out = new StringBuilder();
        for (byte b : value) out.append(String.format("%02x", b & 255));
        return out.toString();
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("APK expected-signer-sha256 device-sdk");
        int sdk = Integer.parseInt(args[2]);
        ApkVerifier.Result result = new ApkVerifier.Builder(new File(args[0]))
            .setMinCheckedPlatformVersion(sdk).setMaxCheckedPlatformVersion(sdk).build().verify();
        if (!result.isVerified() || result.containsErrors()) {
            throw new SecurityException("APK verification failed: " + result.getAllErrors());
        }
        Set<String> authenticated = new LinkedHashSet<>();
        for (X509Certificate cert : result.getSignerCertificates()) authenticated.add(digest(cert));
        SigningCertificateLineage lineage = result.getSigningCertificateLineage();
        if (lineage != null) {
            for (X509Certificate cert : lineage.getCertificatesInLineage()) authenticated.add(digest(cert));
        }
        if (!authenticated.contains(args[1].toLowerCase())) {
            throw new SecurityException("Published signer absent from verified signing lineage: " + authenticated);
        }
        System.out.println("VERIFIED sdk=" + sdk + " authenticated-signers=" + String.join(",", authenticated));
    }
}
