import QtQuick
import QtTest
import qs.Commons
import qs.Commons as Commons

TestCase {
  name: "EqCurve"
  width: 600; height: 360
  visible: true
  when: windowShown
  EqCurveEditor { id: editor; x: 20; y: 20; width: 300; height: 260 }
  SignalSpy { id: saved; target: editor; signalName: "released" }
  function entry(id) {
    return {eq_id:id,name:"Curve",min_gain_db:-6,max_gain_db:6,
      bands:[{frequency_hz:62,gain_db:0},{frequency_hz:250,gain_db:1},
        {frequency_hz:1000,gain_db:-1},{frequency_hz:4000,gain_db:2},
        {frequency_hz:8000,gain_db:4},{frequency_hz:16000,gain_db:6}]}
  }
  function init() {
    editor.enabled = true
    editor.contextKey = "pair-a"
    editor.entry = entry(7)
    editor.settle()
    Commons.Color.accent = "#5060e0"
    saved.clear()
    wait(0)
  }
  function test_drag_only_saves_changed_curve_on_release_and_snaps() {
    var handle = findChild(editor,"eqHandle_62")
    mousePress(handle,handle.width/2,handle.height/2)
    mouseMove(handle,handle.width/2,-500,20)
    compare(saved.count,0)
    compare(editor.gains[0],6)
    mouseRelease(handle,handle.width/2,-500)
    compare(saved.count,1)
    compare(saved.signalArguments[0][0],7)
    compare(saved.signalArguments[0][1].join(","),"6,1,-1,2,4,6")
    compare(saved.signalArguments[0][2],"pair-a")
    editor.settle()
    handle = findChild(editor,"eqHandle_62")
    mouseClick(handle,handle.width/2,handle.height/2)
    compare(saved.count,1) // Clicking without a gain change does not write.
  }
  function test_same_entry_poll_does_not_reset_drag_but_identity_change_cancels() {
    var handle = findChild(editor,"eqHandle_62")
    mousePress(handle,handle.width/2,handle.height/2)
    mouseMove(handle,handle.width/2,-30,20)
    var preview=editor.gains[0]
    editor.entry = entry(7)
    compare(editor.gains[0],preview)
    editor.contextKey = "pair-b"
    mouseRelease(handle,handle.width/2,-30)
    compare(saved.count,0)
    compare(editor.gains[0],0)
  }
  function test_same_entry_poll_preserves_pointer_grab_until_release() {
    var handle=findChild(editor,"eqHandle_62")
    mousePress(handle,handle.width/2,handle.height/2)
    mouseMove(handle,handle.width/2,-30,20)
    var preview=editor.gains[0]
    editor.entry=entry(7)
    wait(0)
    compare(editor.activeIndex,0)
    compare(editor.gains[0],preview)
    mouseRelease(handle,handle.width/2,handle.height/2)
    compare(saved.count,1)
  }
  function test_disabled_or_changed_slot_cancels_without_saving() {
    for (var change of ["slot","disabled"]) {
      editor.enabled=true; editor.entry=entry(7); editor.settle()
      var handle=findChild(editor,"eqHandle_62")
      mousePress(handle,handle.width/2,handle.height/2)
      mouseMove(handle,handle.width/2,-40,20)
      if(change==="slot") editor.entry=entry(8)
      else editor.enabled=false
      mouseRelease(handle,handle.width/2,-40)
      compare(saved.count,0)
      compare(editor.gains[0],0)
    }
  }
  function test_keyboard_changes_save_at_key_release_and_theme_updates_handles() {
    var handle=findChild(editor,"eqHandle_62")
    handle.forceActiveFocus()
    keyPress(Qt.Key_Up)
    compare(saved.count,0)
    compare(editor.gains[0],1)
    keyRelease(Qt.Key_Up)
    compare(saved.count,1)
    Commons.Color.accent="#e04090"
    compare(findChild(editor,"eqPoint_62").border.color,Qt.color("#e04090"))
    compare(findChild(editor,"eqCurveStroke").strokeColor,Qt.color("#e04090"))
  }
}
