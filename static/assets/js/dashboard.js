
  // Your existing modal open/close logic
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
  }

  function closeModal(modal) {
    modal.classList.remove('active');
  }

  document.querySelectorAll('.open-modal-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-modal');
      openModal(modalId);
    });
  });

  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-overlay')) {
        closeModal(modal);
      }
    });

    modal.querySelector('.close-btn').addEventListener('click', () => {
      closeModal(modal);
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll('.modal-overlay.active').forEach(modal => {
        closeModal(modal);
      });
    }
  });

  // CSRF token fetcher
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Toastify function
 function showToast(message, type = "success") {
  Toastify({
    text: message,
    duration: 3000,
    close: true,
    gravity: "top",
    position: "center",
    style: {
      background: type === "success" ? "#28a745" : "#dc3545",
      color: "#fff"  // optional, ensures text is readable
    }
  }).showToast();
}



// search and pagination
function initializeTablePagination({ tableId, searchInputId, paginationId, rowsPerPage = 10 }) {
    const table = document.getElementById(tableId);
    const searchInput = document.getElementById(searchInputId);
    const pagination = document.getElementById(paginationId);

    if (!table || !searchInput || !pagination) return;

    const allRows = Array.from(table.querySelectorAll("tbody tr"));
    let filteredRows = [...allRows];
    let currentPage = 1;

    function displayRows(rows) {
        allRows.forEach(row => row.style.display = "none");
        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        rows.slice(start, end).forEach(row => row.style.display = "");
    }

    function paginate(rows) {
        const pageCount = Math.ceil(rows.length / rowsPerPage);
        pagination.innerHTML = "";

        if (pageCount <= 1) return;

        // Prev Button
        const prevLi = document.createElement("li");
        const prevBtn = document.createElement("button");
        prevBtn.textContent = "« Prev";
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => {
            if (currentPage > 1) {
                currentPage--;
                updateDisplay();
            }
        };
        prevLi.appendChild(prevBtn);
        pagination.appendChild(prevLi);

        // Page Numbers
        for (let i = 1; i <= pageCount; i++) {
            const li = document.createElement("li");
            const btn = document.createElement("button");
            btn.textContent = i;
            if (i === currentPage) btn.classList.add("active");
            btn.addEventListener("click", () => {
                currentPage = i;
                updateDisplay();
            });
            li.appendChild(btn);
            pagination.appendChild(li);
        }

        // Next Button
        const nextLi = document.createElement("li");
        const nextBtn = document.createElement("button");
        nextBtn.textContent = "Next »";
        nextBtn.disabled = currentPage === pageCount;
        nextBtn.onclick = () => {
            if (currentPage < pageCount) {
                currentPage++;
                updateDisplay();
            }
        };
        nextLi.appendChild(nextBtn);
        pagination.appendChild(nextLi);
    }

    function updateDisplay() {
        displayRows(filteredRows);
        paginate(filteredRows);
    }

    // Search
    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim().toLowerCase();
        filteredRows = allRows.filter(row =>
            row.textContent.toLowerCase().includes(query)
        );
        currentPage = 1;
        updateDisplay();
    });

    // Init
    updateDisplay();
}
