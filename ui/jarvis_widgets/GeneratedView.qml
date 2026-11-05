import QtQuick
import "ViewSchema.js" as Schema

Item {
    id: view
    property var specification: ({state: {}, computed: {}, layout: {type: "text", text: ""}})
    property var formState: ({})
    property bool busy: false
    signal stateEdited(var values)
    signal submitted(string prompt, var values)
    implicitHeight: tree.implicitHeight
    onSpecificationChanged: formState = Object.assign({}, specification.state || {})
    Component.onCompleted: formState = Object.assign({}, specification.state || {})
    function value(expression) { return Schema.resolve(expression, formState, specification.computed || {}); }
    function format(text) { return Schema.format(text, formState, specification.computed || {}); }
    function edit(key, value) {
        formState = Object.assign({}, formState, {[key]: value});
        stateEdited(formState);
    }
    ViewNode {
        id: tree
        width: parent.width
        node: view.specification.layout
        context: view
    }
}
