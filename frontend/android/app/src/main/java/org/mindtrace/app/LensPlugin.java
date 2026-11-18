package org.mindtrace.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "MindTraceLens")
public class LensPlugin extends Plugin {
    @PluginMethod
    public void open(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            Intent lens = new Intent(Intent.ACTION_MAIN)
                .addCategory(Intent.CATEGORY_LAUNCHER)
                .setPackage("com.google.ar.lens");
            Intent google = new Intent(Intent.ACTION_VIEW, Uri.parse("googleapp://lens"))
                .setPackage("com.google.android.googlequicksearchbox");
            String mode = launch(lens) || launch(google) ? "camera"
                : launch(new Intent(Intent.ACTION_VIEW, Uri.parse("https://lens.google.com/"))) ? "web" : null;
            if (mode == null) {
                call.reject("Couldn’t open Google Lens. Install Google Lens or a browser.");
                return;
            }
            JSObject result = new JSObject();
            result.put("mode", mode);
            call.resolve(result);
        });
    }

    private boolean launch(Intent intent) {
        try {
            getActivity().startActivity(intent);
            return true;
        } catch (ActivityNotFoundException | SecurityException unavailable) {
            return false;
        }
    }
}
