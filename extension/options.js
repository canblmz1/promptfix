document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.sync.get({ serviceUrl: "http://127.0.0.1:52849" }, (syncItems) => {
    document.getElementById("serviceUrl").value = syncItems.serviceUrl;
  });
  chrome.storage.local.get({ serviceToken: "" }, (localItems) => {
    document.getElementById("serviceToken").value = localItems.serviceToken;
  });
});

document.getElementById("save").addEventListener("click", () => {
  const serviceUrl = document.getElementById("serviceUrl").value.trim();
  const serviceToken = document.getElementById("serviceToken").value.trim();
  chrome.storage.sync.set({ serviceUrl }, () => {
    chrome.storage.local.set({ serviceToken }, () => {
      document.getElementById("status").textContent = "Saved!";
      document.getElementById("status").style.color = "#4ade80";
    });
  });
});

document.getElementById("test").addEventListener("click", async () => {
  const serviceUrl = document.getElementById("serviceUrl").value.trim().replace(/\/+$/, "");
  const status = document.getElementById("status");
  status.textContent = "Testing...";
  status.style.color = "#e0e0e0";

  try {
    const resp = await fetch(`${serviceUrl}/health`);
    if (resp.ok) {
      const data = await resp.json();
      status.textContent = `Connected! v${data.version}`;
      status.style.color = "#4ade80";
    } else {
      status.textContent = `Failed: HTTP ${resp.status}`;
      status.style.color = "#cf222e";
    }
  } catch (e) {
    status.textContent = `Cannot connect: ${e.message}`;
    status.style.color = "#cf222e";
  }
});
