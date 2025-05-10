import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';

let cachedProxy = null;
let proxyExpireTs = 0;

const CACHE_FILE = path.resolve('./cache/proxy.txt');

function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}

function loadProxyFromFile() {
  try {
    if (fs.existsSync(CACHE_FILE)) {
      const [proxy, ts] = fs.readFileSync(CACHE_FILE, 'utf-8').trim().split('|');
      const now = Date.now() / 1000;
      if (proxy && Number(ts) - now > 15) {
        cachedProxy = proxy;
        proxyExpireTs = Number(ts);
        console.log('📂 Loaded cached proxy from file');
      }
    }
  } catch (err) {
    console.warn(`⚠️ Failed to load proxy from file: ${err.message}`);
  }
}

function saveProxyToFile(proxyUrl, expiresAt) {
  try {
    const content = `${proxyUrl}|${expiresAt}`;
    fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
    fs.writeFileSync(CACHE_FILE, content, 'utf-8');
    console.log('💾 Saved proxy to cache file');
  } catch (err) {
    console.warn(`⚠️ Failed to save proxy to file: ${err.message}`);
  }
}

export async function getRotatingProxy(retryCount = 0, maxRetry = 3) {
  return "http://1234568:1234568@1.54.234.249:23270";
  const now = Date.now() / 1000;

  // Lần đầu khởi động, load từ file nếu chưa có
  if (!cachedProxy && fs.existsSync(CACHE_FILE)) {
    loadProxyFromFile();
  }

  // Dùng lại nếu proxy còn sống
  if (cachedProxy && proxyExpireTs - now > 15) {
    console.log('✅ Reusing valid cached proxy');
    return cachedProxy;
  }

  try {
    const res = await fetch('https://proxyxoay.org/api/get.php?key=WQFISlkMuFcCNPSEsmjIyX&&nhamang=random&&tinhthanh=0');
    const data = await res.json();

    if (data.status === 100 && data.proxyhttp) {
      const [ip, port, user, pass] = data.proxyhttp.split(':');
      const proxyUrl = `http://${user}:${pass}@${ip}:${port}`;

      const secondsMatch = data.message.match(/sau (\d+)s/);
      const expiresIn = secondsMatch ? parseInt(secondsMatch[1]) : 600;

      cachedProxy = proxyUrl;
      proxyExpireTs = now + expiresIn;

      saveProxyToFile(proxyUrl, proxyExpireTs);
      console.log(`✅ New proxy acquired, expires in ${expiresIn}s`);
      return proxyUrl;
    } else if (data.message && /sau (\d+)s/.test(data.message)) {
      const waitSeconds = parseInt(data.message.match(/sau (\d+)s/)[1]);

      if (cachedProxy) {
        console.warn(`⚠️ Proxy chưa thể đổi (${data.message}), dùng lại proxy cũ`);
        return cachedProxy;
      }

      if (retryCount < maxRetry) {
        console.warn(`⏳ Waiting ${waitSeconds}s then retrying (${retryCount + 1}/${maxRetry})...`);
        await sleep(waitSeconds);
        return getRotatingProxy(retryCount + 1, maxRetry);
      } else {
        throw new Error(`❌ Retry limit reached. Proxy fetch failed after waiting.`);
      }
    } else {
      throw new Error(`❌ Proxy fetch failed: ${data.message || 'Unknown error'}`);
    }
  } catch (err) {
    if (cachedProxy) {
      console.warn(`⚠️ Error occurred: ${err.message}, falling back to cached proxy`);
      return cachedProxy;
    }
    throw err;
  }
}
