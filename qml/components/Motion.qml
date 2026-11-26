pragma Singleton
import QtQuick

//: The app's motion scale, in Windows UI (WinUI 3) terms.
//:
//: One vocabulary for every state change, the way `Spacing` is one vocabulary
//: for insets. The durations are the documented WinUI 3 control durations, and
//: `enter` is its documented incoming spline — "Timing and easing" on Microsoft
//: Learn: Fast Out, Slow In. (WinUI's outgoing spline is the mirror image; the
//: app's reveals are property tweens that run the same curve in both
//: directions, so only one is needed here.)
//:
//: Qt has no named equivalent: `Easing.OutCubic` starts slower and lands softer
//: than (0, 0, 0, 1), so an animation written with it reads as a different
//: design language next to the WinUI controls. Write state changes with
//: `easing.type: Easing.BezierSpline` and `easing.bezierCurve: Motion.enter`,
//: and take the duration from here as well.
//:
//: `slide` is the one distance a Segmented content switch travels. The
//: Calculator's Code/Assign stage and its Result/Plot pane both use it with a
//: cross-fade, so the two controls cannot drift into different transitions.
QtObject {
    //: ControlFastAnimationDuration — a control changing state (hover, a pane
    //: switching under a Segmented).
    readonly property int fast: 167
    //: ControlNormalAnimationDuration — a panel opening or closing.
    readonly property int normal: 250
    //: ControlFasterAnimationDuration — feedback that must not lag the pointer.
    readonly property int faster: 83
    //: cubic-bezier(0, 0, 0, 1): UI entering the scene (WinUI's decelerate).
    readonly property var enter: [0, 0, 0, 1, 1, 1]
    //: The single left/right travel of a Segmented content switch, in px.
    readonly property int slide: 40
}
