// Non-Python repository file.
// The migration pipeline should detect this as JavaScript and not translate it
// during the Python 2 -> Python 3 MVP.

function renderInvoice(invoice) {
    return {
        customer: invoice.customer,
        total: invoice.total
    };
}

module.exports = {
    renderInvoice: renderInvoice
};
