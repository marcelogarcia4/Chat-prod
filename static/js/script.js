document.addEventListener('DOMContentLoaded', () => {
    // Corrected IDs to match HTML
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const productDisplayArea = document.getElementById('product-display-area');
    const chatSpinner = document.getElementById('chat-spinner');
    const productSpinner = document.getElementById('product-spinner');
    const productErrorMessage = document.getElementById('product-error-message');

    // Corrected API URLs to match Flask backend port
    const CHAT_API_URL = 'http://localhost:5000/api/chat';
    const PRODUCT_SEARCH_API_URL = 'http://localhost:5000/api/search-products';

    let conversationHistory = [];

    // --- Helper Functions ---
    function displayMessage(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', sender === 'user' ? 'user-message' : 'ai-message');

        // Sanitize message content before inserting as HTML (basic sanitization)
        // Using DOMParser for robust HTML sanitization is better for production
        const tempDiv = document.createElement('div');
        tempDiv.textContent = message; // Use textContent to prevent XSS
        messageElement.innerHTML = tempDiv.innerHTML.replace(/\n/g, '<br>'); // Replace newlines with <br> for display

        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll to bottom
    }

    function showChatSpinner(show) {
        chatSpinner.style.display = show ? 'block' : 'none';
    }

    function showProductSpinner(show) {
        productSpinner.style.display = show ? 'block' : 'none';
    }

    function showProductError(message) {
        productErrorMessage.textContent = message;
        productErrorMessage.style.display = 'block';
        productDisplayArea.innerHTML = ''; // Clear any existing products
    }

    function hideProductError() {
        productErrorMessage.style.display = 'none';
    }

    function extractSource(productUrl) {
        if (!productUrl) return 'Other'; // Changed 'Otro' to 'Other' for consistency
        try {
            const url = new URL(productUrl);
            const hostname = url.hostname.toLowerCase();
            if (hostname.includes('amazon.')) return 'Amazon';
            if (hostname.includes('ebay.')) return 'eBay';
            if (hostname.includes('walmart.')) return 'Walmart';
            if (hostname.includes('target.')) return 'Target';
            if (hostname.includes('bestbuy.')) return 'Best Buy';
            if (hostname.includes('shopee.')) return 'Shopee';
            if (hostname.includes('aliexpress.')) return 'AliExpress';
            // Capitalize first letter of the domain if not a known source
            const domainParts = hostname.replace(/^www\./, '').split('.');
            return domainParts[0].charAt(0).toUpperCase() + domainParts[0].slice(1);
        } catch (e) {
            return 'Other';
        }
    }

    // --- API Interaction ---
    async function handleSendMessage() {
        const userMessageText = userInput.value.trim();
        if (!userMessageText) return;

        displayMessage('user', userMessageText);
        conversationHistory.push({ role: 'user', content: userMessageText });
        userInput.value = '';
        showChatSpinner(true);
        hideProductError(); // Hide previous product errors
        productDisplayArea.innerHTML = ''; // Clear previous products on new chat message

        try {
            const response = await fetch(CHAT_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: conversationHistory }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ reply: "An unknown error occurred with the AI service." }));
                throw new Error(errorData.error || `AI service error: ${response.status}`);
            }

            const data = await response.json();

            // Only display AI reply if it's not a pure search action JSON
            if (!(data.action && data.action.action === 'search' && data.action.keywords)) {
                 displayMessage('ai', data.reply);
                 conversationHistory.push({ role: 'assistant', content: data.reply });
            } else {
                 // If it's a search action, AI might have sent "Okay, searching now!" or similar.
                 // We add that to history, but might not display it explicitly if the search starts immediately.
                 // For now, let's keep it simple and assume the backend sends a friendly text reply for search initiation.
                 // Or, you can explicitly display something like:
                 displayMessage('ai', "Okay, I'm searching for products based on your request!");
                 conversationHistory.push({ role: 'assistant', content: data.reply || "Okay, I'm searching for products based on your request!" }); // Add the actual AI reply for history
            }


            if (data.action && data.action.action === 'search' && data.action.keywords) {
                // AI indicated a search action
                await searchProducts(data.action.keywords);
            }

        } catch (error) {
            console.error('Error sending message:', error);
            displayMessage('ai', `Sorry, I encountered an error: ${error.message}`);
            conversationHistory.push({ role: 'assistant', content: `Error: ${error.message}` });
        } finally {
            showChatSpinner(false);
        }
    }

    async function searchProducts(keywords) {
        if (!keywords || keywords.length === 0) {
            showProductError("The AI didn't provide any keywords to search for.");
            return;
        }

        showProductSpinner(true);
        productDisplayArea.innerHTML = ''; // Clear previous results
        hideProductError();

        const query = keywords.join(' ');
        try {
            const response = await fetch(`${PRODUCT_SEARCH_API_URL}?q=${encodeURIComponent(query)}`);

            if (!response.ok) {
                 const errorData = await response.json().catch(() => ({ error: "Failed to fetch products. Invalid server response." }));
                throw new Error(errorData.error || `Product API error: ${response.status}`);
            }

            const productsData = await response.json(); // This should now be the array of products or empty array

            displayProducts(productsData);

        } catch (error) {
            console.error('Error fetching products:', error);
            showProductError(`Failed to fetch products: ${error.message}`);
        } finally {
            showProductSpinner(false);
        }
    }

    // --- Product Display ---
    function displayProducts(products) { // Renamed from productsData to products for clarity
        productDisplayArea.innerHTML = ''; // Clear previous products or loading messages
        hideProductError();

        if (!products || products.length === 0) {
            showProductError('No products found matching your criteria. Try rephrasing your request or being more specific.');
            return;
        }

        products.forEach(product => {
            const productCard = `
                <div class="col-md-4 col-sm-6 mb-4">
                    <div class="card product-card h-100">
                        <img src="${(product.product_photos && product.product_photos[0]) || 'https://via.placeholder.com/200x150.png?text=No+Image'}" class="card-img-top" alt="${product.product_title}">
                        <div class="card-body">
                            <h5 class="card-title" title="${product.product_title}">${product.product_title}</h5>
                            <p class="card-text price">${product.offer && product.offer.price ? product.offer.price : 'Price not available'}</p>
                            <p class="card-text source">Source: ${extractSource(product.offer ? product.offer.offer_page_url : product.product_url)}</p>
                        </div>
                        <div class="card-footer text-center">
                             <a href="${product.offer ? product.offer.offer_page_url : product.product_url || '#'}" target="_blank" class="btn btn-success w-100">View Product</a>
                        </div>
                    </div>
                </div>
            `;
            productDisplayArea.insertAdjacentHTML('beforeend', productCard);
        });
    }

    // --- Event Listeners ---
    sendButton.addEventListener('click', handleSendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            handleSendMessage();
        }
    });

    // --- Initial AI Greeting ---
    function initialGreeting() {
        const greeting = "Hello! I'm your AI Product Assistant. How can I help you find the perfect product today?";
        conversationHistory.push({ role: 'assistant', content: greeting });
        displayMessage('ai', greeting);
    }

    initialGreeting();
});
