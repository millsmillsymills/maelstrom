# 🌐 **MAELSTROM.LOCAL ACCESS SOLUTION**

## 🔍 **ISSUE DIAGNOSIS**

**Problem**: Cannot load https://maelstrom.local from Chrome on client machine 192.168.1.191

**Root Causes Identified:**
1. **DNS Resolution**: Client machine doesn't know that `maelstrom.local` points to `192.168.1.239`
2. **SSL Certificate Trust**: Browser doesn't trust the self-signed certificate
3. **Missing Hosts Entry**: Local domain not configured in client's hosts file

---

## ✅ **SOLUTION STEPS**

### **Step 1: Add Hosts File Entries (CRITICAL)**

**For Windows Client (192.168.1.191):**

1. **Open Command Prompt as Administrator**
   - Press `Win + R`, type `cmd`, press `Ctrl + Shift + Enter`

2. **Add Domain Entries:**
   ```cmd
   echo # Maelstrom Monitoring >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 grafana.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 prometheus.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 wazuh.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 zabbix.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 alertmanager.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 influxdb.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 loki.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   echo 192.168.1.239 cadvisor.maelstrom.local >> C:\Windows\System32\drivers\etc\hosts
   ```

**For Linux/Mac Client:**
```bash
sudo bash -c 'cat >> /etc/hosts << EOF
# Maelstrom Monitoring
192.168.1.239 maelstrom.local
192.168.1.239 grafana.maelstrom.local
192.168.1.239 prometheus.maelstrom.local
192.168.1.239 wazuh.maelstrom.local
192.168.1.239 zabbix.maelstrom.local
192.168.1.239 alertmanager.maelstrom.local
192.168.1.239 influxdb.maelstrom.local
192.168.1.239 loki.maelstrom.local
192.168.1.239 cadvisor.maelstrom.local
EOF'
```

### **Step 2: Handle SSL Certificate Warning**

**When you first visit https://maelstrom.local:**

1. **Chrome will show "Your connection is not private"**
2. **Click "Advanced"**
3. **Click "Proceed to maelstrom.local (unsafe)"**

**Alternative: Add Certificate Exception**
1. Navigate to https://maelstrom.local
2. Click the lock icon → "Certificate is not valid"
3. Go to "Details" → "Export Certificate"
4. Install certificate in "Trusted Root Certification Authorities"

### **Step 3: Verify Access**

After completing steps 1 and 2, test these URLs:

- **Main Portal**: https://maelstrom.local (redirects to Grafana)
- **Grafana Dashboard**: https://grafana.maelstrom.local
- **Prometheus Metrics**: https://prometheus.maelstrom.local
- **Health Check**: https://maelstrom.local/health

---

## 🔧 **TROUBLESHOOTING**

### **If Still Not Working:**

**1. Flush DNS Cache:**
```cmd
# Windows
ipconfig /flushdns

# Linux/Mac
sudo dnsmasq --clear-cache
# or
sudo systemctl restart systemd-resolved
```

**2. Test Network Connectivity:**
```cmd
# Test if server is reachable
ping 192.168.1.239

# Test if ports are open
telnet 192.168.1.239 443
telnet 192.168.1.239 80
```

**3. Verify Hosts File:**
```cmd
# Windows
type C:\Windows\System32\drivers\etc\hosts | findstr maelstrom

# Linux/Mac
cat /etc/hosts | grep maelstrom
```

**4. Browser Alternative:**
If Chrome continues to have issues, try:
- **Firefox**: Often more permissive with self-signed certificates
- **Edge**: Alternative browser test
- **Incognito Mode**: Bypasses some cache issues

---

## 🎯 **EXPECTED RESULTS**

After following these steps:

1. **https://maelstrom.local** → Redirects to Grafana dashboard
2. **https://grafana.maelstrom.local** → Grafana login page
3. **https://maelstrom.local/health** → Returns "SWAG Reverse Proxy - maelstrom.local - OK"

---

## 📊 **SERVICE STATUS VERIFICATION**

**Current Server Configuration:**
- **Server IP**: 192.168.1.239
- **SWAG Status**: Running (4+ hours uptime)
- **SSL Certificates**: Self-signed, generated successfully
- **Ports**: 80 (HTTP) and 443 (HTTPS) listening
- **Default Action**: Root domain redirects to Grafana

**Network Test Results:**
- ✅ HTTP (port 80): Returns 301 redirect to HTTPS
- ✅ HTTPS (port 443): Returns 301 redirect to Grafana
- ✅ Self-signed certificate: Generated and active

---

## 🔐 **SECURITY NOTES**

**Why Self-Signed Certificates:**
- `.local` domains cannot get public SSL certificates from Let's Encrypt
- Self-signed certificates provide encryption but require manual trust
- This is standard practice for internal/local domain infrastructure

**Certificate Details:**
- **Issuer**: Linuxserver.io (SWAG default)
- **Subject**: Wildcard certificate for *.maelstrom.local
- **Encryption**: RSA 2048-bit

---

## 🚀 **QUICK TEST**

**Immediate Verification Steps:**
1. Add hosts entries (Step 1)
2. Open Chrome
3. Navigate to: https://maelstrom.local
4. Accept certificate warning
5. Should redirect to Grafana dashboard

**Expected Flow:**
`https://maelstrom.local` → `SSL Warning (Accept)` → `https://grafana.maelstrom.local` → `Grafana Login`

---

*The main issue is DNS resolution - your client machine doesn't know that maelstrom.local points to 192.168.1.239. Once the hosts file is updated, everything should work perfectly!*
