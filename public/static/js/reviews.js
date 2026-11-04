const reviewList = document.querySelector("#review-list");
const errorMessage = document.querySelector("#error-message");
const resultsCount = document.querySelector("#results-count");
const pageStatus = document.querySelector("#page-status");
const previousButton = document.querySelector("#previous-page");
const nextButton = document.querySelector("#next-page");
const filters = document.querySelector("#filters");
const searchInput = document.querySelector("#search");
let currentPage = 1;
let totalPages = 1;
let searchTimer;

document.querySelector("#year").textContent = new Date().getFullYear();

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

function addText(parent, tagName, className, value) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = value;
  parent.append(element);
  return element;
}

function formatDate(timestamp) {
  if (timestamp === null || timestamp === undefined) return "Date unavailable";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request could not be completed.");
  return data;
}

async function loadSummary() {
  try {
    const data = await fetchJson("/api/summary");
    document.querySelector("#metric-reviews").textContent = formatNumber(data.total_reviews);
    document.querySelector("#metric-products").textContent = formatNumber(data.reviewed_products);
    document.querySelector("#metric-rating").textContent = `${Number(data.average_rating).toFixed(2)} / 5`;
    const verifiedPercentage = data.total_reviews
      ? Math.round((data.verified_reviews / data.total_reviews) * 100)
      : 0;
    document.querySelector("#metric-verified").textContent = `${verifiedPercentage}%`;
  } catch (error) {
    showError(error.message);
  }
}

function renderReview(review) {
  const card = document.createElement("article");
  card.className = "review-card";

  const topLine = document.createElement("div");
  topLine.className = "review-topline";
  addText(topLine, "h3", "review-title", review.review_title || "Untitled review");
  addText(topLine, "span", "rating", `${"★".repeat(Math.round(review.rating || 0))}${"☆".repeat(5 - Math.round(review.rating || 0))}  ${(review.rating ?? "—")}/5`);
  card.append(topLine);

  const productLine = document.createElement("div");
  productLine.className = "review-product-line";
  addText(productLine, "span", "product-id", review.product_id || "Unknown product");
  addText(productLine, "span", "", "·");
  addText(productLine, "span", "", review.product_title || "Product details unavailable");
  if (review.main_category) {
    addText(productLine, "span", "", `· ${review.main_category}`);
  }
  card.append(productLine);

  addText(card, "p", "review-text", review.review_text || "No written review was provided.");

  const meta = document.createElement("div");
  meta.className = "review-meta";
  addText(meta, "span", "", formatDate(review.timestamp));
  if (review.verified_purchase) {
    addText(meta, "span", "verified-tag", "✓ Verified purchase");
  } else {
    addText(meta, "span", "", "Purchase not verified");
  }
  addText(meta, "span", "", `${formatNumber(review.helpful_vote || 0)} found helpful`);
  card.append(meta);

  return card;
}

async function loadReviews() {
  reviewList.setAttribute("aria-busy", "true");
  errorMessage.hidden = true;

  const params = new URLSearchParams(new FormData(filters));
  params.set("page", String(currentPage));

  try {
    const data = await fetchJson(`/api/reviews?${params.toString()}`);
    reviewList.replaceChildren();
    if (data.reviews.length === 0) {
      addText(reviewList, "p", "empty-state", "No reviews match these filters. Try changing your search.");
    } else {
      const fragment = document.createDocumentFragment();
      data.reviews.forEach((review) => fragment.append(renderReview(review)));
      reviewList.append(fragment);
    }

    currentPage = data.page;
    totalPages = data.total_pages;
    resultsCount.textContent = `${formatNumber(data.total)} ${data.total === 1 ? "review" : "reviews"} found`;
    pageStatus.textContent = `Page ${formatNumber(currentPage)} of ${formatNumber(totalPages)}`;
    previousButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
  } catch (error) {
    reviewList.replaceChildren();
    resultsCount.textContent = "Reviews could not be loaded";
    pageStatus.textContent = "Page 1 of 1";
    previousButton.disabled = true;
    nextButton.disabled = true;
    showError(error.message);
  } finally {
    reviewList.setAttribute("aria-busy", "false");
  }
}

filters.addEventListener("change", (event) => {
  if (event.target !== searchInput) {
    currentPage = 1;
    loadReviews();
  }
});

searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    currentPage = 1;
    loadReviews();
  }, 300);
});

previousButton.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    loadReviews();
  }
});

nextButton.addEventListener("click", () => {
  if (currentPage < totalPages) {
    currentPage += 1;
    loadReviews();
  }
});

loadSummary();
loadReviews();
