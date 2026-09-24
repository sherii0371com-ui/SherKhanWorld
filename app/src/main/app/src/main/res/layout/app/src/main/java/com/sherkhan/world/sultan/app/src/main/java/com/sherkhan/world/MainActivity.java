package com.sherkhan.world;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import com.sherkhan.world.sultan.SultanEngine;

public class MainActivity extends AppCompatActivity {

    private TextView txtConsole;
    private Button btnWhatsApp, btnMarketScan, btnGenerateReel;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        txtConsole = findViewById(R.id.txtConsole);
        btnWhatsApp = findViewById(R.id.btnWhatsApp);
        btnMarketScan = findViewById(R.id.btnMarketScan);
        btnGenerateReel = findViewById(R.id.btnGenerateReel);

        // Initialize Sultan Core
        String status = SultanEngine.initializeNeuralSync();
        appendConsole(status);

        btnWhatsApp.setOnClickListener(v -> {
            appendConsole("[Sultan WhatsApp]: Opening Direct Secure Channel...");
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/"));
                startActivity(intent);
            } catch (Exception e) {
                Toast.makeText(this, "WhatsApp integration ready.", Toast.LENGTH_SHORT).show();
            }
        });

        btnMarketScan.setOnClickListener(v -> {
            String scanResult = SultanEngine.scanPakistanMarket();
            appendConsole(scanResult);
        });

        btnGenerateReel.setOnClickListener(v -> {
            String reelResult = SultanEngine.generateReelPipeline("Bazaar, Rider, Food, Jewelry, Homes, Hospitals & Quran 30 Paras");
            appendConsole(reelResult);
            Toast.makeText(this, "Reel Generated & Branded with SherKhanWorld!", Toast.LENGTH_LONG).show();
        });
    }

    private void appendConsole(String message) {
        String current = txtConsole.getText().toString();
        txtConsole.setText(current + "\n\n" + message);
    }
}
