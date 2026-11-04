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

const productModeTab = document.querySelector("#product-mode-tab");
const shopperModeTab = document.querySelector("#shopper-mode-tab");
const productMode = document.querySelector("#product-mode");
const shopperMode = document.querySelector("#shopper-mode");
const cartList = document.querySelector("#cart-list");
const cartCount = document.querySelector("#cart-count");
const cartTotal = document.querySelector("#cart-total");
const cartStatus = document.querySelector("#cart-status");
const routeButton = document.querySelector("#find-route");
const finishShoppingButton = document.querySelector("#finish-shopping");
const mapCells = document.querySelector("#map-cells");
const mapMarkers = document.querySelector("#map-markers");
const routeLine = document.querySelector("#route-line");
const routeLabels = document.querySelector("#route-labels");
const routeSteps = document.querySelector("#route-steps");
const routeMessage = document.querySelector("#route-message");
const directionsList = document.querySelector("#walking-directions");
const checkoutDialog = document.querySelector("#checkout-dialog");
const checkoutForm = document.querySelector("#checkout-form");
const checkoutError = document.querySelector("#checkout-error");
const submitFeedbackButton = document.querySelector("#submit-feedback");
const feedbackList = document.querySelector("#shopper-feedback-list");
const feedbackCount = document.querySelector("#shopper-feedback-count");
const cart = new Map();
let shopperStartedAt = Date.now();
let shopperSessionStarted = false;

const storeProducts = [
  { id: "milk", name: "Whole Milk", aisle: 2, category: "Dairy", price: 3.79, target: [4, 3], shelf: [4, 2] },
  { id: "bread", name: "Sourdough Bread", aisle: 1, category: "Bakery", price: 5.49, target: [1, 3], shelf: [1, 2] },
  { id: "coffee", name: "Arabica Coffee", aisle: 3, category: "Coffee", price: 12.99, target: [7, 6], shelf: [7, 5] },
  { id: "oats", name: "Organic Oats", aisle: 2, category: "Breakfast", price: 4.29, target: [4, 6], shelf: [4, 5] },
];

const storeGrid = [
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
];

const entrance = [0, 0];
const checkout = [9, 9];
const svgNamespace = "http://www.w3.org/2000/svg";

function setActiveMode(mode) {
  const isShopperMode = mode === "shopper";
  productMode.hidden = isShopperMode;
  shopperMode.hidden = !isShopperMode;
  productModeTab.classList.toggle("is-active", !isShopperMode);
  shopperModeTab.classList.toggle("is-active", isShopperMode);
  productModeTab.setAttribute("aria-selected", String(!isShopperMode));
  shopperModeTab.setAttribute("aria-selected", String(isShopperMode));

  if (isShopperMode && !shopperSessionStarted) {
    shopperStartedAt = Date.now();
    shopperSessionStarted = true;
  }
}

productModeTab.addEventListener("click", () => setActiveMode("product"));
shopperModeTab.addEventListener("click", () => setActiveMode("shopper"));

function createSvgElement(tagName, attributes = {}) {
  const element = document.createElementNS(svgNamespace, tagName);
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, String(value)));
  return element;
}

function drawStoreGrid() {
  const fragment = document.createDocumentFragment();
  storeGrid.forEach((row, rowIndex) => {
    row.forEach((cell, columnIndex) => {
      const classes = ["map-cell", cell === 1 ? "shelf" : "walkable"];
      if (rowIndex === entrance[0] && columnIndex === entrance[1]) classes.push("entrance");
      if (rowIndex === checkout[0] && columnIndex === checkout[1]) classes.push("checkout");
      fragment.append(createSvgElement("rect", {
        x: columnIndex * 50 + 3,
        y: rowIndex * 50 + 3,
        width: 44,
        height: 44,
        rx: 5,
        class: classes.join(" "),
      }));

      if ((rowIndex === entrance[0] && columnIndex === entrance[1])
        || (rowIndex === checkout[0] && columnIndex === checkout[1])) {
        const label = createSvgElement("text", {
          x: columnIndex * 50 + 25,
          y: rowIndex * 50 + 25,
          class: "map-cell-label",
        });
        label.textContent = rowIndex === entrance[0] && columnIndex === entrance[1] ? "IN" : "OUT";
        fragment.append(label);
      }
    });
  });
  mapCells.replaceChildren(fragment);
}

function productForId(productId) {
  return storeProducts.find((product) => product.id === productId);
}

function renderCart() {
  const totalQuantity = [...cart.values()].reduce((sum, quantity) => sum + quantity, 0);
  const cartProducts = [...cart.entries()]
    .map(([id, quantity]) => ({ product: productForId(id), quantity }))
    .filter((entry) => entry.product);

  cartCount.textContent = `${totalQuantity} ${totalQuantity === 1 ? "item" : "items"}`;
  cartTotal.textContent = `$${cartProducts.reduce(
    (sum, entry) => sum + entry.product.price * entry.quantity,
    0,
  ).toFixed(2)}`;
  routeButton.disabled = cartProducts.length === 0;
  finishShoppingButton.disabled = cartProducts.length === 0;

  if (cartProducts.length === 0) {
    const emptyMessage = document.createElement("p");
    emptyMessage.className = "cart-empty";
    emptyMessage.textContent = "Your cart is empty. Add a grocery item to get started.";
    cartList.replaceChildren(emptyMessage);
    cartStatus.textContent = "Add items to plan your route.";
    mapMarkers.replaceChildren();
    resetRoute("Add items to your cart, then find your shortest route.");
    return;
  }

  const cartFragment = document.createDocumentFragment();
  cartProducts.forEach(({ product, quantity }) => {
    const row = document.createElement("div");
    row.className = "cart-row";
    addText(row, "span", "cart-row-name", `${product.name}${quantity > 1 ? ` × ${quantity}` : ""}`);
    addText(row, "span", "cart-row-price", `$${(product.price * quantity).toFixed(2)}`);
    const removeButton = document.createElement("button");
    removeButton.className = "remove-from-cart";
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", `Remove ${product.name} from cart`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      cart.delete(product.id);
      renderCart();
    });
    row.append(removeButton);
    cartFragment.append(row);
  });
  cartList.replaceChildren(cartFragment);
  cartStatus.textContent = `${cartProducts.length} ${cartProducts.length === 1 ? "stop" : "stops"} on your map.`;
  renderItemPins(cartProducts.map((entry) => entry.product));
  resetRoute("Cart updated. Find your shortest route when you are ready.");
}

function renderItemPins(products) {
  const fragment = document.createDocumentFragment();
  products.forEach((product, index) => {
    const [row, column] = product.shelf;
    const x = column * 50 + 25;
    const y = row * 50 + 25;
    fragment.append(createSvgElement("circle", { cx: x, cy: y, r: 13, class: "item-pin" }));
    const label = createSvgElement("text", { x, y, class: "item-pin-label" });
    label.textContent = String(index + 1);
    fragment.append(label);
  });
  mapMarkers.replaceChildren(fragment);
}

function pointKey(point) {
  return `${point[0]},${point[1]}`;
}

function manhattanDistance(first, second) {
  return Math.abs(first[0] - second[0]) + Math.abs(first[1] - second[1]);
}

function findPath(start, goal) {
  const keyFor = pointKey;
  const startKey = keyFor(start);
  const goalKey = keyFor(goal);
  const openSet = [{ point: start, score: manhattanDistance(start, goal) }];
  const cameFrom = new Map();
  const costs = new Map([[startKey, 0]]);
  const closed = new Set();
  const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];

  while (openSet.length) {
    openSet.sort((a, b) => a.score - b.score);
    const current = openSet.shift().point;
    const currentKey = keyFor(current);
    if (closed.has(currentKey)) continue;
    if (currentKey === goalKey) {
      const path = [current];
      let traceKey = currentKey;
      while (cameFrom.has(traceKey)) {
        traceKey = cameFrom.get(traceKey);
        path.push(traceKey.split(",").map(Number));
      }
      return path.reverse();
    }

    closed.add(currentKey);
    directions.forEach(([rowStep, columnStep]) => {
      const neighbor = [current[0] + rowStep, current[1] + columnStep];
      const [row, column] = neighbor;
      if (row < 0 || column < 0 || row >= storeGrid.length
        || column >= storeGrid[0].length || storeGrid[row][column] !== 0) return;

      const neighborKey = keyFor(neighbor);
      const tentativeCost = costs.get(currentKey) + 1;
      if (tentativeCost >= (costs.get(neighborKey) ?? Number.POSITIVE_INFINITY)) return;
      cameFrom.set(neighborKey, currentKey);
      costs.set(neighborKey, tentativeCost);
      openSet.push({
        point: neighbor,
        score: tentativeCost + manhattanDistance(neighbor, goal),
      });
    });
  }

  return null;
}

function planShoppingRoute() {
  const remaining = [...cart.keys()].map(productForId).filter(Boolean);
  if (remaining.length === 0) return null;

  let current = entrance;
  const fullPath = [entrance];
  const legs = [];
  while (remaining.length) {
    let closestIndex = -1;
    let closestPath = null;
    remaining.forEach((product, index) => {
      const candidate = findPath(current, product.target);
      if (candidate && (!closestPath || candidate.length < closestPath.length)) {
        closestIndex = index;
        closestPath = candidate;
      }
    });
    if (closestIndex < 0 || !closestPath) return null;

    const product = remaining.splice(closestIndex, 1)[0];
    fullPath.push(...closestPath.slice(1));
    legs.push({ product, path: closestPath });
    current = product.target;
  }

  const checkoutPath = findPath(current, checkout);
  if (!checkoutPath) return null;
  fullPath.push(...checkoutPath.slice(1));
  legs.push({ product: { name: "Checkout" }, path: checkoutPath });
  return { path: fullPath, legs };
}

function appendRouteDirections(legs) {
  const fragment = document.createDocumentFragment();
  let currentName = "Entrance";
  legs.forEach(({ product, path }) => {
    const runs = [];
    for (let index = 1; index < path.length; index += 1) {
      const previous = path[index - 1];
      const next = path[index];
      const dr = next[0] - previous[0];
      const dc = next[1] - previous[1];
      const direction = dr === -1 ? "north" : dr === 1 ? "south" : dc === -1 ? "west" : "east";
      const lastRun = runs[runs.length - 1];
      if (lastRun && lastRun.direction === direction) lastRun.steps += 1;
      else runs.push({ direction, steps: 1 });
    }

    const listItem = document.createElement("li");
    const movement = runs.length
      ? runs.map((run) => `${run.direction} ${run.steps} ${run.steps === 1 ? "step" : "steps"}`).join(", then ")
      : "stay here";
    const stopName = product.name === "Checkout"
      ? "Checkout"
      : `${product.name} (Aisle ${product.aisle})`;
    listItem.textContent = `From ${currentName}, go ${movement} to ${stopName}.`;
    fragment.append(listItem);
    currentName = product.name;
  });
  directionsList.replaceChildren(fragment);
}

function drawPlannedRoute(route) {
  const points = route.path.map(([row, column]) => `${column * 50 + 25},${row * 50 + 25}`).join(" ");
  routeLine.setAttribute("points", points);
  routeLine.classList.remove("is-animated");
  routeLine.style.strokeDashoffset = "";
  const routeLength = routeLine.getTotalLength();
  routeLine.style.strokeDasharray = `${routeLength}`;
  routeLine.style.strokeDashoffset = `${routeLength}`;

  const stopFragment = document.createDocumentFragment();
  const stops = [
    { point: entrance, label: "IN" },
    ...route.legs.slice(0, -1).map((leg, index) => ({
      point: leg.product.target,
      label: String(index + 1),
    })),
    { point: checkout, label: "OUT" },
  ];
  stops.forEach(({ point, label }) => {
    const [row, column] = point;
    const x = column * 50 + 25;
    const y = row * 50 + 25;
    stopFragment.append(createSvgElement("circle", { cx: x, cy: y, r: 10, class: "route-stop" }));
    const markerLabel = createSvgElement("text", { x, y, class: "route-stop-label" });
    markerLabel.textContent = label;
    stopFragment.append(markerLabel);
  });
  routeLabels.replaceChildren(stopFragment);
  requestAnimationFrame(() => {
    routeLine.classList.add("is-animated");
    routeLine.style.strokeDashoffset = "0";
  });
}

function resetRoute(message) {
  routeLine.setAttribute("points", "");
  routeLine.classList.remove("is-animated");
  routeLine.style.strokeDasharray = "";
  routeLine.style.strokeDashoffset = "";
  routeLabels.replaceChildren();
  routeSteps.textContent = "—";
  routeMessage.textContent = message;
  const item = document.createElement("li");
  item.textContent = "Your directions will appear here.";
  directionsList.replaceChildren(item);
}

function findShortestRoute() {
  const route = planShoppingRoute();
  if (!route) {
    cartStatus.textContent = "No walkable route could be found. Please update your cart and try again.";
    resetRoute("The selected stops could not be connected on the store map.");
    return;
  }

  drawPlannedRoute(route);
  appendRouteDirections(route.legs);
  const steps = route.path.length - 1;
  routeSteps.textContent = `${steps} ${steps === 1 ? "step" : "steps"}`;
  routeMessage.textContent = `Entrance → ${route.legs.slice(0, -1).map((leg) => leg.product.name).join(" → ")} → Checkout`;
  cartStatus.textContent = "Shortest route planned from entrance to checkout.";
}

document.querySelectorAll("[data-add-to-cart]").forEach((button) => {
  button.addEventListener("click", () => {
    const product = productForId(button.dataset.addToCart);
    if (!product) return;
    cart.set(product.id, (cart.get(product.id) || 0) + 1);
    renderCart();
  });
});

routeButton.addEventListener("click", findShortestRoute);

function renderShopperFeedback(review, prepend = false) {
  const card = document.createElement("article");
  card.className = "shopper-feedback-card";

  const topLine = document.createElement("div");
  topLine.className = "shopper-feedback-topline";
  addText(topLine, "strong", "", review.customer_name || "Aislewise shopper");
  const sentiment = (review.sentiment || "").toLowerCase();
  const sentimentBadge = addText(
    topLine,
    "span",
    `sentiment-badge ${sentiment === "positive" ? "sentiment-positive" : "sentiment-negative"}`,
    `${sentiment || "unknown"} · AI`,
  );
  sentimentBadge.setAttribute("aria-label", `AI sentiment: ${sentiment || "unknown"}`);
  card.append(topLine);

  addText(card, "div", "shopper-feedback-stars", `${"★".repeat(Number(review.rating) || 0)}${"☆".repeat(5 - (Number(review.rating) || 0))}`);
  addText(card, "p", "shopper-feedback-text", review.review_text || "No written feedback.");
  const meta = document.createElement("div");
  meta.className = "shopper-feedback-meta";
  addText(meta, "span", "", formatDate(review.created_at));
  if (Number.isFinite(Number(review.dwell_time_seconds))) {
    addText(meta, "span", "", `${formatNumber(Number(review.dwell_time_seconds))} sec in store`);
  }
  card.append(meta);

  if (prepend && feedbackList.firstChild) feedbackList.insertBefore(card, feedbackList.firstChild);
  else feedbackList.append(card);
}

async function loadShopperFeedback() {
  try {
    const data = await fetchJson("/api/shopper-reviews");
    feedbackList.replaceChildren();
    data.reviews.forEach((review) => renderShopperFeedback(review));
    feedbackCount.textContent = `${formatNumber(data.total)} ${data.total === 1 ? "review" : "reviews"}`;
    if (data.reviews.length === 0) {
      addText(feedbackList, "p", "shopper-feedback-empty", "No shopper feedback yet. Finish a trip to leave the first review.");
    }
  } catch (error) {
    feedbackList.replaceChildren();
    addText(feedbackList, "p", "shopper-feedback-error", error.message);
    feedbackCount.textContent = "Unavailable";
  }
}

function openCheckout() {
  checkoutError.hidden = true;
  checkoutError.textContent = "";
  document.querySelector("#review-dwell-time").value = String(
    Math.max(0, Math.floor((Date.now() - shopperStartedAt) / 1000)),
  );
  checkoutDialog.showModal();
  document.querySelector("#customer-name").focus();
}

function closeCheckout() {
  checkoutDialog.close();
}

finishShoppingButton.addEventListener("click", openCheckout);
document.querySelector("#close-checkout").addEventListener("click", closeCheckout);
document.querySelector("#cancel-checkout").addEventListener("click", closeCheckout);

checkoutForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  checkoutError.hidden = true;
  if (!checkoutForm.reportValidity()) return;

  const submitLabel = submitFeedbackButton.textContent;
  submitFeedbackButton.disabled = true;
  submitFeedbackButton.textContent = "Submitting…";
  const payload = {
    customer_name: document.querySelector("#customer-name").value.trim(),
    rating: Number(document.querySelector("#shopper-rating").value),
    review_text: document.querySelector("#shopper-review-text").value.trim(),
    dwell_time_seconds: Number(document.querySelector("#review-dwell-time").value),
    cart_items: [...cart.keys()],
  };

  try {
    const response = await fetch("/api/reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
    throw new Error(data.error || "Feedback could not be saved.");
}

console.log("Shopper feedback API response:", data);

if (!data.review || typeof data.review !== "object") {
    throw new Error(
        "Feedback was received, but the API did not return the saved review. Check the Flask response."
    );
}

const emptyState = feedbackList.querySelector(
    ".shopper-feedback-empty, .shopper-feedback-error"
);

if (emptyState) emptyState.remove();

renderShopperFeedback(data.review, true);
    const priorCount = Number.parseInt(feedbackCount.textContent, 10) || 0;
    feedbackCount.textContent = `${formatNumber(priorCount + 1)} ${priorCount === 0 ? "review" : "reviews"}`;
    checkoutForm.reset();
    checkoutDialog.close();
    setActiveMode("product");
    cart.clear();
    renderCart();
    shopperStartedAt = Date.now();
    shopperSessionStarted = false;
  } catch (error) {
    checkoutError.textContent = error.message;
    checkoutError.hidden = false;
  } finally {
    submitFeedbackButton.disabled = false;
    submitFeedbackButton.textContent = submitLabel;
  }
});

drawStoreGrid();
renderCart();
loadShopperFeedback();
