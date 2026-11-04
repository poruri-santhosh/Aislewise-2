
checkoutForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  checkoutError.hidden = true;
  checkoutError.textContent = "";

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
    // Submit feedback to Flask
    const response = await fetch("/api/shopper-reviews", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify(payload),
    });

    // Safely parse the API response
    const responseText = await response.text();

    console.log("Shopper feedback HTTP status:", response.status);
    console.log("Shopper feedback response:", responseText);

    let data;

    try {
      data = JSON.parse(responseText);
    } catch {
      throw new Error(
        "Flask returned HTML instead of JSON. Check the Flask terminal."
      );
    }

    if (!response.ok) {
      throw new Error(
        data.error || "Feedback could not be saved."
      );
    }

    if (!data.review || typeof data.review !== "object") {
      throw new Error(
        "API did not return the saved review. Check the Flask POST route."
      );
    }

    // Remove empty/error messages
    const emptyState = feedbackList.querySelector(
      ".shopper-feedback-empty, .shopper-feedback-error"
    );

    if (emptyState) emptyState.remove();

    // Display saved feedback
    renderShopperFeedback(data.review, true);

    // Update feedback count
    const priorCount =
      Number.parseInt(feedbackCount.textContent, 10) || 0;

    feedbackCount.textContent =
      `${formatNumber(priorCount + 1)} ${priorCount === 0 ? "review" : "reviews"}`;

    // Reset checkout
    checkoutForm.reset();
    checkoutDialog.close();

    setActiveMode("product");

    cart.clear();
    renderCart();

    shopperStartedAt = Date.now();
    shopperSessionStarted = false;

  } catch (error) {
    console.error("Checkout feedback error:", error);

    checkoutError.textContent = error.message;
    checkoutError.hidden = false;

  } finally {
    submitFeedbackButton.disabled = false;
    submitFeedbackButton.textContent = submitLabel;
  }
});
