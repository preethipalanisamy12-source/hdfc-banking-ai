const API = "";

// Application state
let currentUser = null;
let selectedCustomer = null;
let currentPage = "dashboard";

const $ = (id) => document.getElementById(id);


// ==================================================
// API HELPER
// ==================================================

async function apiRequest(url, options = {}) {
    const response = await fetch(API + url, {
        credentials: "include",
        ...options,
        headers: {
            ...(options.headers || {})
        }
    });

    const contentType = response.headers.get("content-type") || "";

    const data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

    if (!response.ok) {
        const message =
            typeof data === "object"
                ? data.detail || data.message || "Request failed"
                : data;

        throw new Error(message);
    }

    return data;
}


// ==================================================
// UTILITIES
// ==================================================

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

function formatMoney(value) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(Number(value || 0));
}

function formatDate(value) {
    if (!value) return "-";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "-";

    return date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short"
    });
}

function initials(name) {
    return String(name || "User")
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map(word => word[0])
        .join("")
        .toUpperCase();
}

function showToast(message) {
    const toast = $("toast");

    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2800);
}

function showError(container, message) {
    container.innerHTML = `
        <div class="inline-error">
            ${escapeHTML(message)}
        </div>
    `;
}

function statusBadge(status) {
    const value = String(status || "UNKNOWN").toUpperCase();

    let className = "status";

    if (value === "SUCCESS" || value === "ACTIVE") {
        className += " status-success";
    } else if (
        value === "FAILED" ||
        value === "BLOCKED" ||
        value === "INACTIVE"
    ) {
        className += " status-failed";
    } else if (value === "PENDING") {
        className += " status-pending";
    }

    return `<span class="${className}">${escapeHTML(value)}</span>`;
}


// ==================================================
// LOGIN
// ==================================================

$("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const button = $("loginButton");
    const error = $("loginError");

    error.textContent = "";
    button.disabled = true;
    button.textContent = "Signing in...";

    const email = $("email").value.trim();
    const password = $("password").value;

    try {
        const data = await apiRequest("/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email,
                password
            })
        });

        currentUser = data.user;

        if (!currentUser || !currentUser.role) {
            throw new Error("User role was not returned by the login API.");
        }

        currentUser.role = currentUser.role.toUpperCase();

        if (!["CUSTOMER", "ADMIN"].includes(currentUser.role)) {
            throw new Error("Unsupported user role.");
        }

        await openDashboard();

        showToast("Welcome back!");

    } catch (err) {
        error.textContent = err.message;
    } finally {
        button.disabled = false;
        button.innerHTML = 'Sign in <span>→</span>';
    }
});


// Show/hide password
$("togglePassword").addEventListener("click", () => {
    const input = $("password");

    if (input.type === "password") {
        input.type = "text";
        $("togglePassword").textContent = "Hide";
    } else {
        input.type = "password";
        $("togglePassword").textContent = "Show";
    }
});


// ==================================================
// SESSION RESTORE
// ==================================================

async function restoreSession() {
    try {
        const profile = await apiRequest("/api/profile/me");

        currentUser = {
            ...profile,
            role: "CUSTOMER"
        };

        try {
            await apiRequest("/api/admin/dashboard");
            currentUser.role = "ADMIN";
        } catch {
            currentUser.role = "CUSTOMER";
        }

        await openDashboard();

    } catch {
        $("loginView").classList.remove("hidden");
        $("appView").classList.add("hidden");
    }
}


// ==================================================
// OPEN DASHBOARD
// ==================================================

async function openDashboard() {
    $("loginView").classList.add("hidden");
    $("appView").classList.remove("hidden");

    $("topUserName").textContent =
        currentUser.full_name ||
        currentUser.name ||
        currentUser.email;

    $("topUserRole").textContent = currentUser.role;

    $("topAvatar").textContent = initials(
        currentUser.full_name || currentUser.email
    );

    $("chatToggle").classList.remove("hidden");

    if (currentUser.role === "ADMIN") {
        setupAdminNavigation();
        await loadAdminDashboard();
    } else {
        setupCustomerNavigation();
        await loadCustomerDashboard();
    }
}


// ==================================================
// NAVIGATION
// ==================================================

function setPageTitle(title) {
    $("pageTitle").textContent = title;
}

function setupCustomerNavigation() {
    $("sideNav").innerHTML = `
        <button class="nav-link active" data-page="dashboard">
            <span class="nav-icon">⌂</span> Overview
        </button>

        <button class="nav-link" data-page="transactions">
            <span class="nav-icon">↔</span> Transactions
        </button>

        <button class="nav-link" data-page="profile">
            <span class="nav-icon">◎</span> My Profile
        </button>
    `;

    attachNavigationEvents();
}

function setupAdminNavigation() {
    $("sideNav").innerHTML = `
        <button class="nav-link active" data-page="dashboard">
            <span class="nav-icon">⌂</span> Overview
        </button>

        <button class="nav-link" data-page="customers">
            <span class="nav-icon">♙</span> Customers
        </button>

        <button class="nav-link" data-page="accounts">
            <span class="nav-icon">▣</span> Accounts
        </button>

        <button class="nav-link" data-page="transactions">
            <span class="nav-icon">↔</span> Transactions
        </button>
    `;

    attachNavigationEvents();
}

function attachNavigationEvents() {
    document.querySelectorAll(".nav-link").forEach(button => {
        button.addEventListener("click", async () => {
            document.querySelectorAll(".nav-link").forEach(item => {
                item.classList.remove("active");
            });

            button.classList.add("active");

            currentPage = button.dataset.page;

            if (currentUser.role === "ADMIN") {
                await loadAdminPage(currentPage);
            } else {
                await loadCustomerPage(currentPage);
            }

            $("sidebar").classList.remove("open");
        });
    });
}

$("mobileMenu").addEventListener("click", () => {
    $("sidebar").classList.toggle("open");
});


// ==================================================
// CUSTOMER DASHBOARD
// ==================================================

async function loadCustomerDashboard() {
    await loadCustomerPage("dashboard");
}

async function loadCustomerPage(page) {
    const container = $("customerPage");

    container.classList.remove("hidden");
    $("adminPage").classList.add("hidden");

    try {
        if (page === "dashboard") {
            setPageTitle("My Banking Overview");
            await renderCustomerDashboard(container);
        }

        if (page === "transactions") {
            setPageTitle("My Transactions");
            await renderCustomerTransactions(container);
        }

        if (page === "profile") {
            setPageTitle("My Profile");
            await renderCustomerProfile(container);
        }

    } catch (err) {
        showError(container, err.message);
    }
}

async function getCustomerData() {
    const [profile, banking] = await Promise.all([
        apiRequest("/api/profile/me"),
        apiRequest("/api/transactions/my-data")
    ]);

    return { profile, banking };
}


// ==================================================
// CUSTOMER DASHBOARD RENDERING
// ==================================================

async function renderCustomerDashboard(container) {
    container.innerHTML = `
        <div class="loading">
            Loading your banking information...
        </div>
    `;

    const { profile, banking } = await getCustomerData();

    const name =
        profile.full_name ||
        profile.name ||
        currentUser.email;

    const city = profile.city || "";

    // Correctly extract rows from the API response
    const accounts = Array.isArray(banking.accounts)
        ? banking.accounts
        : (banking.accounts?.rows || []);

    const summaryRows = Array.isArray(banking.transaction_summary)
        ? banking.transaction_summary
        : (banking.transaction_summary?.rows || []);

    const summary = summaryRows[0] || {};

    const transactions = Array.isArray(banking.recent_transactions)
        ? banking.recent_transactions
        : (banking.recent_transactions?.rows || []);

    const account = accounts[0] || {};

    currentUser.full_name = name;

    $("topUserName").textContent = name;
    $("topAvatar").textContent = initials(name);

    const balance =
        account.balance ??
        summary.balance ??
        summary.current_balance ??
        0;

    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>Welcome, ${escapeHTML(name)}</h1>
                <p>
                    Your banking overview
                    ${city ? "· " + escapeHTML(city) : ""}
                </p>
            </div>
        </div>

        <div class="account-card">
            <div class="account-label">
                TOTAL ACCOUNT BALANCE
            </div>

            <div class="account-balance">
                ${formatMoney(balance)}
            </div>

            <div class="account-details">
                <div>
                    <small>ACCOUNT NUMBER</small>
                    <strong>
                        ${escapeHTML(
                            account.account_number_masked ||
                            account.account_number ||
                            "-"
                        )}
                    </strong>
                </div>

                <div>
                    <small>ACCOUNT TYPE</small>
                    <strong>${escapeHTML(account.account_type || "-")}</strong>
                </div>

                <div>
                    <small>ACCOUNT STATUS</small>
                    <strong>${escapeHTML(account.account_status || "-")}</strong>
                </div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Transactions</div>
                <div class="stat-value">
                    ${Number(summary.total_transactions || transactions.length)}
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Successful</div>
                <div class="stat-value">
                    ${Number(summary.successful_transactions || 0)}
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <div>
                    <h3>Recent Transactions</h3>
                    <p>Your latest banking activity</p>
                </div>

                <button
                    class="panel-link"
                    id="viewAllCustomerTransactions"
                >
                    View all →
                </button>
            </div>

            ${transactionTable(transactions.slice(0, 5))}
        </div>
    `;

    $("viewAllCustomerTransactions").addEventListener("click", () => {
        document.querySelector('[data-page="transactions"]').click();
    });
}


// ==================================================
// TRANSACTION TABLE
// ==================================================

function transactionTable(transactions) {
    if (!Array.isArray(transactions) || !transactions.length) {
        return `<div class="empty-state">No transactions found.</div>`;
    }

    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Reference</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Date</th>
                        <th>Status</th>
                    </tr>
                </thead>

                <tbody>
                    ${transactions.map(tx => {
                        const reference =
                            tx.reference_number ??
                            tx.transaction_id ??
                            tx.txn_id ??
                            "-";

                        const type =
                            tx.transaction_type ??
                            tx.type ??
                            "-";

                        const date =
                            tx.transaction_date ??
                            tx.date;

                        const status =
                            tx.transaction_status ??
                            tx.status;

                        return `
                            <tr>
                                <td>${escapeHTML(reference)}</td>

                                <td>
                                    <span class="${
                                        String(type).toUpperCase() === "CREDIT"
                                            ? "credit"
                                            : "debit"
                                    }">
                                        ${escapeHTML(type)}
                                    </span>
                                </td>

                                <td>${formatMoney(tx.amount)}</td>

                                <td>${formatDate(date)}</td>

                                <td>${statusBadge(status)}</td>
                            </tr>
                        `;
                    }).join("")}
                </tbody>
            </table>
        </div>
    `;
}


// ==================================================
// CUSTOMER TRANSACTIONS
// ==================================================

async function renderCustomerTransactions(container) {
    container.innerHTML = `
        <div class="loading">Loading transactions...</div>
    `;

    const data = await apiRequest("/api/transactions/my-data");

    const transactions = Array.isArray(data.recent_transactions)
        ? data.recent_transactions
        : (data.recent_transactions?.rows || []);

    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>Transaction History</h1>
                <p>All your available transaction records</p>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h3>My Transactions</h3>
                <span class="status">
                    ${transactions.length} Records
                </span>
            </div>

            ${transactionTable(transactions)}
        </div>
    `;
}


// ==================================================
// CUSTOMER PROFILE
// ==================================================

async function renderCustomerProfile(container) {
    container.innerHTML = `
        <div class="loading">Loading profile...</div>
    `;

    const profile = await apiRequest("/api/profile/me");

    const name = profile.full_name || profile.name || "-";

    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>My Profile</h1>
                <p>Your registered banking information</p>
            </div>
        </div>

        <div class="profile-banner">
            <div class="profile-avatar">${initials(name)}</div>

            <div>
                <h2>${escapeHTML(name)}</h2>
                <p>${escapeHTML(profile.email || currentUser.email)}</p>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h3>Personal Information</h3>
            </div>

            <table>
                <tbody>
                    <tr>
                        <th>Customer ID</th>
                        <td>${escapeHTML(profile.customer_id || "-")}</td>
                    </tr>

                    <tr>
                        <th>Customer Code</th>
                        <td>${escapeHTML(profile.customer_code || "-")}</td>
                    </tr>

                    <tr>
                        <th>Full Name</th>
                        <td>${escapeHTML(name)}</td>
                    </tr>

                    <tr>
                        <th>Email</th>
                        <td>${escapeHTML(profile.email || "-")}</td>
                    </tr>

                    <tr>
                        <th>Phone</th>
                        <td>${escapeHTML(profile.phone || "-")}</td>
                    </tr>

                    <tr>
                        <th>City</th>
                        <td>${escapeHTML(profile.city || "-")}</td>
                    </tr>

                    <tr>
                        <th>Status</th>
                        <td>${statusBadge(profile.customer_status)}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    `;
}


// ==================================================
// ADMIN DASHBOARD
// ==================================================

async function loadAdminDashboard() {
    await loadAdminPage("dashboard");
}

async function loadAdminPage(page) {
    const container = $("adminPage");

    container.classList.remove("hidden");
    $("customerPage").classList.add("hidden");

    try {
        if (page === "dashboard") {
            setPageTitle("Admin Overview");
            await renderAdminDashboard(container);
        }

        if (page === "customers") {
            setPageTitle("Customer Management");
            await renderAdminCustomers(container);
        }

        if (page === "accounts") {
            setPageTitle("All Accounts");
            await renderAdminAccounts(container);
        }

        if (page === "transactions") {
            setPageTitle("All Transactions");
            await renderAdminTransactions(container);
        }

    } catch (err) {
        showError(container, err.message);
    }
}


// ==================================================
// ADMIN DASHBOARD RENDERING
// ==================================================

async function renderAdminDashboard(container) {
    container.innerHTML = `
        <div class="loading">Loading dashboard...</div>
    `;

    try {
        const data = await apiRequest("/api/admin/dashboard");

        container.innerHTML = `
            <div class="page-heading">
                <div>
                    <h1>Admin Dashboard</h1>
                    <p>Banking system overview and customer activity</p>
                </div>
            </div>

            <div class="stats-grid">

                <div class="stat-card">
                    <div class="stat-icon">♙</div>
                    <div class="stat-label">Total Customers</div>
                    <div class="stat-value">
                        ${Number(data.total_customers || 0)}
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon">▣</div>
                    <div class="stat-label">Total Accounts</div>
                    <div class="stat-value">
                        ${Number(data.total_accounts || 0)}
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon">↔</div>
                    <div class="stat-label">Total Transactions</div>
                    <div class="stat-value">
                        ${Number(data.total_transactions || 0)}
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon">✓</div>
                    <div class="stat-label">Successful Transactions</div>
                    <div class="stat-value">
                        ${Number(data.successful_transactions || 0)}
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-label">Failed Transactions</div>
                    <div class="stat-value">
                        ${Number(data.failed_transactions || 0)}
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-label">Pending Transactions</div>
                    <div class="stat-value">
                        ${Number(data.pending_transactions || 0)}
                    </div>
                </div>

            </div>

            <div class="panel">

                <div class="panel-header">
                    <div>
                        <h3>Customer Directory</h3>
                        <p>
                            Select a customer to view their banking activity
                        </p>
                    </div>

                    <button
                        class="panel-link"
                        id="dashboardViewCustomers"
                    >
                        View all →
                    </button>
                </div>

                <div id="dashboardCustomerList" class="loading">
                    Loading customers...
                </div>

            </div>

            <div id="selectedCustomerArea"></div>
        `;

        const customers = await apiRequest("/api/admin/customers");

        renderCustomerList(
            $("dashboardCustomerList"),
            customers.customers || [],
            true
        );

        $("dashboardViewCustomers").addEventListener("click", () => {
            document.querySelector('[data-page="customers"]').click();
        });

    } catch (err) {
        showError(container, err.message);
    }
}


// ==================================================
// ADMIN CUSTOMER DIRECTORY
// ==================================================

async function renderAdminCustomers(container) {
    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>Customer Directory</h1>
                <p>Search and select customers to view their information</p>
            </div>
        </div>

        <div class="panel">
            <div class="toolbar">
                <input
                    type="search"
                    class="search-input"
                    id="customerSearch"
                    placeholder="Search name, code, email or phone..."
                >
            </div>

            <div id="customerResults" class="loading">
                Loading customers...
            </div>
        </div>

        <div id="selectedCustomerArea"></div>
    `;

    const data = await apiRequest("/api/admin/customers");

    renderCustomerList(
        $("customerResults"),
        data.customers || [],
        false
    );

    $("customerSearch").addEventListener("input", async (event) => {
        const query = event.target.value.trim();

        if (query.length < 2) {
            const all = await apiRequest("/api/admin/customers");

            renderCustomerList(
                $("customerResults"),
                all.customers || [],
                false
            );

            return;
        }

        try {
            const results = await apiRequest(
                "/api/admin/customers/search?q=" +
                encodeURIComponent(query)
            );

            renderCustomerList(
                $("customerResults"),
                results.customers || [],
                false
            );

        } catch (err) {
            showError($("customerResults"), err.message);
        }
    });
}


// ==================================================
// CUSTOMER LIST
// ==================================================

function renderCustomerList(container, customers, compact = false) {
    if (!customers.length) {
        container.innerHTML = `
            <div class="empty-state">No customers found.</div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Customer</th>
                        <th>Customer Code</th>
                        <th>Email</th>
                        <th>City</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>

                <tbody>
                    ${customers.map(customer => `
                        <tr>
                            <td>
                                <div class="customer-name">
                                    ${escapeHTML(customer.full_name)}
                                </div>
                            </td>

                            <td>${escapeHTML(customer.customer_code)}</td>

                            <td>${escapeHTML(customer.email)}</td>

                            <td>${escapeHTML(customer.city || "-")}</td>

                            <td>${statusBadge(customer.customer_status)}</td>

                            <td>
                                <button
                                    class="view-button"
                                    data-customer-id="${Number(customer.customer_id)}"
                                >
                                    View details
                                </button>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;

    container.querySelectorAll(".view-button").forEach(button => {
        button.addEventListener("click", () => {
            const id = Number(button.dataset.customerId);

            const customer = customers.find(
                item => Number(item.customer_id) === id
            );

            if (customer) {
                showSelectedCustomer(customer);
            }
        });
    });
}


// ==================================================
// SELECTED CUSTOMER DETAILS
// ==================================================

async function showSelectedCustomer(customer) {
    selectedCustomer = customer;

    const area = $("selectedCustomerArea");

    if (!area) {
        showToast("Customer details area not found.");
        return;
    }

    area.innerHTML = `
        <div class="loading">
            Loading ${escapeHTML(customer.full_name)}...
        </div>
    `;

    try {
        const transactionsData = await apiRequest(
            `/api/admin/customers/${customer.customer_id}/transactions`
        );

        const accountsData = await apiRequest(
            "/api/admin/accounts"
        );

        const accounts = (accountsData.accounts || []).filter(
            account =>
                Number(account.customer_id) ===
                Number(customer.customer_id)
        );

        const transactions = transactionsData.transactions || [];

        area.innerHTML = `
            <div class="panel">

                <button class="back-button" id="closeCustomerDetails">
                    ← Back to customer list
                </button>

                <div class="profile-banner">
                    <div class="profile-avatar">
                        ${initials(customer.full_name)}
                    </div>

                    <div>
                        <h2>${escapeHTML(customer.full_name)}</h2>
                        <p>
                            ${escapeHTML(customer.customer_code)}
                            · ${escapeHTML(customer.email)}
                        </p>
                    </div>
                </div>

                <div class="panel-header">
                    <h3>Customer Account Information</h3>
                </div>

                ${
                    accounts.length
                    ? `
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Account Number</th>
                                        <th>Account Type</th>
                                        <th>Balance</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>

                                <tbody>
                                    ${accounts.map(account => `
                                        <tr>
                                            <td>${escapeHTML(account.account_number_masked || account.account_number || "-")}</td>
                                            <td>${escapeHTML(account.account_type)}</td>
                                            <td>${formatMoney(account.balance)}</td>
                                            <td>${statusBadge(account.account_status)}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    `
                    : `
                        <div class="empty-state">
                            No accounts found for this customer.
                        </div>
                    `
                }

                <div class="panel-header" style="margin-top:25px">
                    <div>
                        <h3>Customer Transactions</h3>
                        <p>
                            ${transactions.length} transactions found
                        </p>
                    </div>
                </div>

                ${transactionTable(transactions)}

            </div>
        `;

        $("closeCustomerDetails").addEventListener("click", () => {
            area.innerHTML = "";
            selectedCustomer = null;
        });

    } catch (err) {
        showError(area, err.message);
    }
}


// ==================================================
// ADMIN ACCOUNTS
// ==================================================

async function renderAdminAccounts(container) {
    container.innerHTML = `
        <div class="loading">Loading accounts...</div>
    `;

    const data = await apiRequest("/api/admin/accounts");

    const accounts = data.accounts || [];

    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>Account Directory</h1>
                <p>View all registered customer accounts</p>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h3>All Accounts (${accounts.length})</h3>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Customer</th>
                            <th>Customer Code</th>
                            <th>Account Number</th>
                            <th>Type</th>
                            <th>Balance</th>
                            <th>Status</th>
                        </tr>
                    </thead>

                    <tbody>
                        ${accounts.map(account => `
                            <tr>
                                <td>${escapeHTML(account.customer_name)}</td>
                                <td>${escapeHTML(account.customer_code)}</td>
                                <td>${escapeHTML(account.account_number)}</td>
                                <td>${escapeHTML(account.account_type)}</td>
                                <td>${formatMoney(account.balance)}</td>
                                <td>${statusBadge(account.account_status)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}


// ==================================================
// ADMIN ALL TRANSACTIONS
// ==================================================

async function renderAdminTransactions(container) {
    container.innerHTML = `
        <div class="loading">Loading transactions...</div>
    `;

    const data = await apiRequest("/api/admin/transactions");

    const transactions = data.transactions || [];

    container.innerHTML = `
        <div class="page-heading">
            <div>
                <h1>All Transactions</h1>
                <p>View transaction activity across all customers</p>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h3>Transaction Records (${transactions.length})</h3>
            </div>

            ${adminTransactionTable(transactions)}
        </div>
    `;
}

function adminTransactionTable(transactions) {
    if (!transactions.length) {
        return `
            <div class="empty-state">No transactions found.</div>
        `;
    }

    return `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Reference</th>
                        <th>Customer</th>
                        <th>Account</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>Date</th>
                        <th>Status</th>
                    </tr>
                </thead>

                <tbody>
                    ${transactions.map(tx => `
                        <tr>
                            <td>${escapeHTML(tx.reference_number)}</td>
                            <td>${escapeHTML(tx.customer_name)}</td>
                            <td>${escapeHTML(tx.account_number)}</td>
                            <td>${escapeHTML(tx.transaction_type)}</td>
                            <td>${formatMoney(tx.amount)}</td>
                            <td>${formatDate(tx.transaction_date)}</td>
                            <td>${statusBadge(tx.transaction_status)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}


// ==================================================
// LOGOUT
// ==================================================

$("logoutButton").addEventListener("click", async () => {
    try {
        await apiRequest("/api/auth/logout", {
            method: "POST"
        });

    } catch (err) {
        showToast("Logout request failed: " + err.message);
        return;
    }

    currentUser = null;
    selectedCustomer = null;

    $("appView").classList.add("hidden");
    $("loginView").classList.remove("hidden");

    $("chatToggle").classList.add("hidden");
    $("chatPanel").classList.add("hidden");

    $("loginForm").reset();

    showToast("Logged out successfully.");
});


// ==================================================
// CHATBOT INTERFACE
// ==================================================

$("chatToggle").addEventListener("click", () => {
    $("chatPanel").classList.toggle("hidden");

    if (!$("chatPanel").classList.contains("hidden")) {
        $("chatInput").focus();
    }
});

$("chatClose").addEventListener("click", () => {
    $("chatPanel").classList.add("hidden");
});

function addChatMessage(message, sender = "bot") {
    const messages = $("chatMessages");
    const element = document.createElement("div");

    element.className =
        sender === "user" ? "user-message" : "bot-message";

    element.textContent = message;

    messages.appendChild(element);
    messages.scrollTop = messages.scrollHeight;

    return element;
}

$("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const input = $("chatInput");
    const sendButton = $("chatForm").querySelector('button[type="submit"]');
    const message = input.value.trim();

    if (!message || sendButton.disabled) return;

    addChatMessage(message, "user");

    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;

    const pendingMessage = addChatMessage("Thinking...");

    try {
        const data = await apiRequest("/api/chat/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        pendingMessage.textContent =
            data.answer || "I couldn't generate a response. Please try again.";

    } catch (err) {
        pendingMessage.textContent =
            "Sorry, I couldn't connect to the banking assistant. Please try again. (" +
            err.message + ")";
    } finally {
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();

        $("chatMessages").scrollTop =
            $("chatMessages").scrollHeight;
    }
});


// ==================================================
// START APPLICATION
// ==================================================

document.addEventListener("DOMContentLoaded", () => {
    restoreSession();
});