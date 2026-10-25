/**
 * BLR HazardPulse — Citizen Mobile Web PWA Form Logic
 * Implements 3-tap rapid emergency reporting, camera capture with mock Edge-AI,
 * auto-geolocation, local storage synchronization, and BBMP grievance handoff.
 */

document.addEventListener("DOMContentLoaded", () => {
  // --- DOM Elements ---
  const geoStatus = document.getElementById("geoStatus");
  const geoCoords = document.getElementById("geoCoords");
  const refreshGeoBtn = document.getElementById("refreshGeoBtn");
  
  const cameraTrigger = document.getElementById("cameraTrigger");
  const cameraInput = document.getElementById("cameraInput");
  const cameraPlaceholder = document.getElementById("cameraPlaceholder");
  const imagePreviewWrap = document.getElementById("imagePreviewWrap");
  const imagePreview = document.getElementById("imagePreview");
  const removePhotoBtn = document.getElementById("removePhotoBtn");
  const aiTagOverlay = document.getElementById("aiTagOverlay");

  const categoryChips = document.querySelectorAll(".category-chip");
  const incidentNotes = document.getElementById("incidentNotes");
  const incidentForm = document.getElementById("incidentForm");
  const ticketsContainer = document.getElementById("ticketsContainer");
  const ticketCount = document.getElementById("ticketCount");

  const toastModal = document.getElementById("toastModal");
  const toastTitle = document.getElementById("toastTitle");
  const toastMsg = document.getElementById("toastMsg");

  // State
  let currentCoords = { lat: 12.9262, lon: 77.6765, landmark: "Bellandur ORR Underpass" };
  let selectedCategory = "waterlogging";
  let hasImage = false;

  // Initial Mock Community Tickets
  const initialTickets = [
    {
      id: "BLR-HAZ-4819",
      category: "waterlogging",
      emoji: "💧",
      title: "Waterlogging >30cm",
      location: "Bellandur Underpass Service Rd",
      time: "4 mins ago",
      status: "DISPATCHED",
      statusClass: "status-dispatched"
    },
    {
      id: "BLR-HAZ-4815",
      category: "gridlock",
      emoji: "🚗",
      title: "Deadlock (0 km/h) Stoppage",
      location: "Ecospace Main Ingress Gate",
      time: "12 mins ago",
      status: "ACTIVE",
      statusClass: "status-active"
    },
    {
      id: "BLR-HAZ-4808",
      category: "road_block",
      emoji: "🛑",
      title: "Downed Utility Branch & Cable",
      location: "Sakra Hospital Access Road",
      time: "26 mins ago",
      status: "DISPATCHED",
      statusClass: "status-dispatched"
    }
  ];

  // Load Tickets from LocalStorage or initialize
  function loadTickets() {
    const stored = localStorage.getItem("blr_smart_city_tickets");
    if (!stored) {
      localStorage.setItem("blr_smart_city_tickets", JSON.stringify(initialTickets));
      return initialTickets;
    }
    try {
      return JSON.parse(stored);
    } catch (e) {
      return initialTickets;
    }
  }

  function renderTickets() {
    const tickets = loadTickets();
    ticketCount.textContent = `${tickets.length} Active`;
    ticketsContainer.innerHTML = "";

    tickets.forEach(ticket => {
      const item = document.createElement("div");
      item.className = "ticket-item";
      item.innerHTML = `
        <div class="ticket-main">
          <div class="ticket-badge-icon">${ticket.emoji}</div>
          <div>
            <div class="ticket-title">${ticket.title}</div>
            <div class="ticket-sub">${ticket.location} • <span style="color:#64748B">${ticket.time}</span></div>
          </div>
        </div>
        <span class="ticket-status ${ticket.statusClass}">${ticket.status}</span>
      `;
      ticketsContainer.appendChild(item);
    });
  }

  // Auto-Geolocation
  function resolveLocation() {
    geoStatus.textContent = "Acquiring GPS Fix...";
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude.toFixed(4);
          const lon = position.coords.longitude.toFixed(4);
          currentCoords = { lat, lon, landmark: "Current User Location" };
          geoStatus.textContent = "High-Precision GPS Locked (±4m)";
          geoCoords.textContent = `${lat}° N, ${lon}° E (ORR Active Sector)`;
        },
        () => {
          // Graceful fallback to Bellandur
          currentCoords = { lat: 12.9262, lon: 77.6765, landmark: "Bellandur ORR Underpass" };
          geoStatus.textContent = "Default Corridor Fixed (Bellandur)";
          geoCoords.textContent = "12.9262° N, 77.6765° E (Bellandur Underpass)";
        },
        { timeout: 4000 }
      );
    } else {
      geoStatus.textContent = "Corridor Preserved (Bellandur)";
      geoCoords.textContent = "12.9262° N, 77.6765° E (Bellandur Underpass)";
    }
  }

  refreshGeoBtn.addEventListener("click", () => {
    refreshGeoBtn.style.transform = "rotate(360deg)";
    resolveLocation();
    setTimeout(() => { refreshGeoBtn.style.transform = "none"; }, 400);
  });

  // Tap 1: Instant Camera Trigger
  cameraTrigger.addEventListener("click", (e) => {
    if (e.target !== removePhotoBtn) {
      cameraInput.click();
    }
  });

  cameraInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        imagePreview.src = event.target.result;
        cameraPlaceholder.style.display = "none";
        imagePreviewWrap.style.display = "block";
        hasImage = true;
        simulateAIVision();
      };
      reader.readAsDataURL(file);
    }
  });

  // Tap on placeholder if no file picked can simulate instant capture demo
  function simulateAIVision() {
    aiTagOverlay.textContent = "🤖 Edge AI: Analyzing...";
    setTimeout(() => {
      aiTagOverlay.textContent = "🤖 Edge AI: Hazard Verified (Confidence: 94.8%)";
    }, 700);
  }

  removePhotoBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    cameraInput.value = "";
    imagePreview.src = "";
    imagePreviewWrap.style.display = "none";
    cameraPlaceholder.style.display = "flex";
    hasImage = false;
  });

  // Tap 2: Category Chips Selection
  categoryChips.forEach(chip => {
    chip.addEventListener("click", () => {
      categoryChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      selectedCategory = chip.dataset.category;

      // Auto-populate mock simulated camera image if empty to provide immediate rich demonstration
      if (!hasImage && selectedCategory === "waterlogging") {
        // Subtle indicator
      }
    });
  });

  // Toast Helper
  function showToast(title, message) {
    toastTitle.textContent = title;
    toastMsg.textContent = message;
    toastModal.classList.add("show");
    setTimeout(() => {
      toastModal.classList.remove("show");
    }, 4500);
  }

  // Tap 3: RED Submit Call to Action
  incidentForm.addEventListener("submit", (e) => {
    e.preventDefault();

    const activeChip = document.querySelector(".category-chip.active");
    const emoji = activeChip ? activeChip.dataset.emoji : "🚨";
    const catTitle = activeChip ? activeChip.querySelector(".chip-title").textContent : "Hazard";
    const notes = incidentNotes.value.trim() || "Observed along Bellandur / ORR arterial";
    
    // Generate simulated ticket
    const ticketId = `BLR-HAZ-${Math.floor(1000 + Math.random() * 9000)}`;
    const newTicket = {
      id: ticketId,
      category: selectedCategory,
      emoji: emoji,
      title: catTitle,
      location: notes.length > 25 ? notes.substring(0, 25) + "..." : notes,
      time: "Just now",
      status: "DISPATCHED",
      statusClass: "status-dispatched",
      coords: currentCoords,
      timestamp: new Date().toISOString()
    };

    // Store in localStorage
    const tickets = loadTickets();
    tickets.unshift(newTicket);
    localStorage.setItem("blr_smart_city_tickets", JSON.stringify(tickets));

    // Render feed update
    renderTickets();

    // Show Confirmation
    showToast("Incident Dispatched!", `Ticket #${ticketId} relayed to BBMP Command Hub & EMS Router.`);

    // Reset Form
    incidentNotes.value = "";
    if (hasImage) {
      removePhotoBtn.click();
    }
  });

  // Init
  resolveLocation();
  renderTickets();
});
