// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2022 Abdullah Tahiri <abdullah.tahiri.yo@gmail.com>     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#pragma once

#include <Gui/BitmapFactory.h>
#include <Gui/Notifications.h>
#include <Gui/Command.h>
#include <Gui/CommandT.h>
#include <Gui/InputHint.h>

#include <Mod/Part/App/Geometry2d.h>

#include <Mod/Sketcher/App/SketchObject.h>

#include "DrawSketchDefaultWidgetController.h"
#include "DrawSketchControllableHandler.h"
#include "Utils.h"

#include "CircleEllipseConstructionMethod.h"

#include <algorithm>
#include <vector>

namespace SketcherGui
{

class DrawSketchHandlerCircle;

namespace ConstructionMethods
{

// The circle's own methods: the first two as CircleEllipseConstructionMethod's, which the arc and the
// ellipse share; a method added here doesn't appear in their tools.
enum class CircleConstructionMethod
{
    Center,
    ThreeRim,
    TwoRim,        // the two ends of a diameter
    TwoTangent,    // two lines picked, then where it sits and its size
    ThreeTangent,  // three lines picked
    End            // Must be the last one
};

}  // namespace ConstructionMethods

using DSHCircleController = DrawSketchDefaultWidgetController<
    DrawSketchHandlerCircle,
    /*SelectModeT*/ StateMachines::ThreeSeekEnd,
    /*PAutoConstraintSize =*/3,
    // The tangent methods use only the third (TwoTangent's size); the first two are configured with
    // every method's, never needed while picking lines.
    /*OnViewParametersT =*/OnViewParameters<3, 6, 3, 3, 3>,  // NOLINT
    /*WidgetParametersT =*/WidgetParameters<0, 0, 0, 0, 0>,  // NOLINT
    /*WidgetCheckboxesT =*/WidgetCheckboxes<0, 0, 0, 0, 0>,  // NOLINT
    /*WidgetComboboxesT =*/WidgetComboboxes<1, 1, 1, 1, 1>,  // NOLINT
    /*WidgetLineEditsT =*/WidgetLineEdits<0, 0, 0, 0, 0>,
    ConstructionMethods::CircleConstructionMethod,
    /*bool PFirstComboboxIsConstructionMethod =*/true>;

using DSHCircleControllerBase = DSHCircleController::ControllerBase;

using DrawSketchHandlerCircleBase = DrawSketchControllableHandler<DSHCircleController>;


class DrawSketchHandlerCircle: public DrawSketchHandlerCircleBase
{
    Q_DECLARE_TR_FUNCTIONS(SketcherGui::DrawSketchHandlerCircle)

    friend DSHCircleController;
    friend DSHCircleControllerBase;

public:
    explicit DrawSketchHandlerCircle(ConstructionMethod constrMethod = ConstructionMethod::Center)
        : DrawSketchHandlerCircleBase(constrMethod)
        , radius(0.0)
        , isDiameter(true)
    {}
    ~DrawSketchHandlerCircle() override = default;

private:
    std::list<Gui::InputHint> getToolHints() const override
    {
        using State = std::pair<ConstructionMethod, SelectMode>;
        using enum Gui::InputHint::UserInput;

        const Gui::InputHint switchModeHint = {tr("%1 switch mode"), {KeyM}};

        return Gui::lookupHints<State>(
            {constructionMethod(), state()},
            {
                // Center method
                {.state = {ConstructionMethod::Center, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick circle center"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::Center, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick rim point"), {MouseLeft}},
                         switchModeHint,
                     }},

                // ThreeRim method
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick first rim point"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick second rim point"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::ThreeRim, SelectMode::SeekThird},
                 .hints =
                     {
                         {tr("%1 pick third rim point"), {MouseLeft}},
                         switchModeHint,
                     }},

                // TwoRim method
                {.state = {ConstructionMethod::TwoRim, SelectMode::SeekFirst},
                 .hints =
                     {
                         {tr("%1 pick one end of the diameter"), {MouseLeft}},
                         switchModeHint,
                     }},
                {.state = {ConstructionMethod::TwoRim, SelectMode::SeekSecond},
                 .hints =
                     {
                         {tr("%1 pick the other end"), {MouseLeft}},
                         switchModeHint,
                     }},

                // Tangent methods
                {.state = {ConstructionMethod::TwoTangent, SelectMode::SeekFirst},
                 .hints = {{tr("%1 pick a line"), {MouseLeft}}, switchModeHint}},
                {.state = {ConstructionMethod::TwoTangent, SelectMode::SeekSecond},
                 .hints = {{tr("%1 pick another line"), {MouseLeft}}, switchModeHint}},
                {.state = {ConstructionMethod::TwoTangent, SelectMode::SeekThird},
                 .hints = {{tr("%1 pick where the circle sits"), {MouseLeft}}, switchModeHint}},
                {.state = {ConstructionMethod::ThreeTangent, SelectMode::SeekFirst},
                 .hints = {{tr("%1 pick a line"), {MouseLeft}}, switchModeHint}},
                {.state = {ConstructionMethod::ThreeTangent, SelectMode::SeekSecond},
                 .hints = {{tr("%1 pick another line"), {MouseLeft}}, switchModeHint}},
                {.state = {ConstructionMethod::ThreeTangent, SelectMode::SeekThird},
                 .hints = {{tr("%1 pick a third line"), {MouseLeft}}, switchModeHint}},
            });
    }

    void updateDataAndDrawToPosition(Base::Vector2d onSketchPos) override
    {
        if (isTangentMethod()) {
            updateTangentCircle(onSketchPos);
            return;
        }

        switch (state()) {
            case SelectMode::SeekFirst: {
                toolWidgetManager.drawPositionAtCursor(onSketchPos);
                if (constructionMethod() == ConstructionMethod::Center) {
                    centerPoint = onSketchPos;

                    seekAndRenderAutoConstraint(sugConstraints[0], onSketchPos, Base::Vector2d());
                }
                else {
                    firstPoint = onSketchPos;

                    seekAndRenderAutoConstraint(
                        sugConstraints[0],
                        onSketchPos,
                        Base::Vector2d(),
                        AutoConstraint::CURVE
                    );
                }
            } break;
            case SelectMode::SeekSecond: {
                if (constructionMethod() == ConstructionMethod::ThreeRim
                    || constructionMethod() == ConstructionMethod::TwoRim) {
                    centerPoint = (onSketchPos - firstPoint) / 2 + firstPoint;
                }
                secondPoint = onSketchPos;

                radius = (onSketchPos - centerPoint).Length();

                CreateAndDrawShapeGeometry();

                if (constructionMethod() == ConstructionMethod::Center) {
                    toolWidgetManager.drawDoubleAtCursor(onSketchPos, radius);
                }
                else {
                    toolWidgetManager.drawPositionAtCursor(onSketchPos);
                }

                seekAndRenderAutoConstraint(
                    sugConstraints[1],
                    onSketchPos,
                    constructionMethod() == ConstructionMethod::Center ? onSketchPos - centerPoint
                                                                       : Base::Vector2d(),
                    AutoConstraint::CURVE
                );
            } break;
            case SelectMode::SeekThird: {
                try {
                    if (areCollinear(firstPoint, secondPoint, onSketchPos)) {
                        // If points are collinear then we can't calculate the center.
                        return;
                    }

                    centerPoint
                        = Part::Geom2dCircle::getCircleCenter(firstPoint, secondPoint, onSketchPos);

                    radius = (onSketchPos - centerPoint).Length();

                    toolWidgetManager.drawPositionAtCursor(onSketchPos);

                    CreateAndDrawShapeGeometry();

                    seekAndRenderAutoConstraint(
                        sugConstraints[2],
                        onSketchPos,
                        Base::Vector2d(0.f, 0.f),
                        AutoConstraint::CURVE
                    );
                }
                catch (Base::ValueError& e) {
                    e.reportException();
                }
            } break;
            default:
                break;
        }
    }

    void executeCommands() override
    {
        try {
            createShape(false);

            openCommand(QT_TRANSLATE_NOOP("Command", "Add sketch circle"));

            commandAddShapeGeometryAndConstraints();

            commitCommand();
        }
        catch (const Base::Exception&) {
            Gui::NotifyError(
                sketchgui,
                QT_TRANSLATE_NOOP("Notifications", "Error"),
                QT_TRANSLATE_NOOP("Notifications", "Failed to add circle")
            );

            abortCommand();
            THROWM(
                Base::RuntimeError,
                QT_TRANSLATE_NOOP(
                    "Notifications",
                    "Tool execution aborted"
                ) "\n"
            )  // This prevents constraints from being
               // applied on non existing geometry
        }
    }

    void generateAutoConstraints() override
    {
        if (isTangentMethod()) {
            return;  // held by its tangencies to the picked lines
        }

        int CircleGeoId = getHighestCurveIndex();

        if (constructionMethod() == ConstructionMethod::Center) {
            auto& ac1 = sugConstraints[0];
            auto& ac2 = sugConstraints[1];

            generateAutoConstraintsOnElement(
                ac1,
                CircleGeoId,
                Sketcher::PointPos::mid
            );  // add auto constraints for the center point
            generateAutoConstraintsOnElement(
                ac2,
                CircleGeoId,
                Sketcher::PointPos::none
            );  // add auto constraints for the edge
        }
        else {

            auto& ac1 = sugConstraints[0];
            auto& ac2 = sugConstraints[1];
            auto& ac3 = sugConstraints[2];

            generateAutoConstraintsOnElement(
                ac1,
                CircleGeoId,
                Sketcher::PointPos::none
            );  // add auto constraints for the first point
            generateAutoConstraintsOnElement(
                ac2,
                CircleGeoId,
                Sketcher::PointPos::none
            );  // add auto constraints for the second point
            generateAutoConstraintsOnElement(
                ac3,
                CircleGeoId,
                Sketcher::PointPos::none
            );  // add auto constraints for the second point
        }

        // Ensure temporary autoconstraints do not generate a redundancy and that the geometry
        // parameters are accurate This is particularly important for adding widget mandated
        // constraints.
        removeRedundantAutoConstraints();
    }

    void createAutoConstraints() override
    {
        // execute python command to create autoconstraints
        createGeneratedAutoConstraints(true);

        sugConstraints[0].clear();
        sugConstraints[1].clear();
        sugConstraints[2].clear();
    }

    std::string getToolName() const override
    {
        return "DSH_Circle";
    }

    QString getCrosshairCursorSVGName() const override
    {
        if (constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::Center) {
            return QStringLiteral("Sketcher_Pointer_Create_Circle");
        }
        else {
            return QStringLiteral("Sketcher_Pointer_Create_3PointCircle");
        }
    }

    std::unique_ptr<QWidget> createWidget() const override
    {
        return std::make_unique<SketcherToolDefaultWidget>();
    }

    bool isWidgetVisible() const override
    {
        return true;
    };

    QPixmap getToolIcon() const override
    {
        return Gui::BitmapFactory().pixmap("Sketcher_CreateCircle");
    }

    QString getToolWidgetText() const override
    {
        return QString(tr("Circle Parameters"));
    }

    bool canGoToNextMode() override
    {
        if (state() == SelectMode::SeekSecond && radius < Precision::Confusion()) {
            // Prevent validation of null circle.
            return false;
        }

        return true;
    }

    // reimplement because circle is 2 steps while 3rims is 3 steps
    void onButtonPressed(Base::Vector2d onSketchPos) override
    {
        this->updateDataAndDrawToPosition(onSketchPos);

        if (isTangentMethod()) {
            if (isPickingLine()) {
                if (hoveredLine == Sketcher::GeoEnum::GeoUndef) {
                    return;  // a click away from any line picks nothing
                }
                tangentLines.push_back(hoveredLine);
                if (state() != SelectMode::SeekThird) {
                    moveToNextMode();
                    return;
                }
                if (radius > Precision::Confusion()) {  // the third line: done
                    setState(SelectMode::End);
                    return;
                }
                tangentLines.pop_back();  // no circle touches these three
                return;
            }
            if (radius > Precision::Confusion()) {  // TwoTangent: where it sits
                setState(SelectMode::End);
            }
            return;
        }
        if (canGoToNextMode()) {
            if (state() == SelectMode::SeekSecond
                && constructionMethod() != ConstructionMethod::ThreeRim) {
                setState(SelectMode::End);
            }
            else {
                moveToNextMode();
            }
        }
    }

    void createShape(bool onlyeditoutline) override
    {
        Q_UNUSED(onlyeditoutline);

        ShapeGeometry.clear();
        ShapeConstraints.clear();

        if (radius < Precision::Confusion()) {
            return;
        }

        addCircleToShapeGeometry(toVector3d(centerPoint), radius, isConstructionMode());

        if (isTangentMethod() && !onlyeditoutline) {
            const int circleId = getHighestCurveIndex() + 1;
            for (int line : tangentLines) {
                addToShapeConstraints(
                    Sketcher::Tangent,
                    circleId,
                    Sketcher::PointPos::none,
                    line,
                    Sketcher::PointPos::none
                );
            }
        }
    }

    void onReset() override
    {
        tangentLines.clear();
        hoveredLine = Sketcher::GeoEnum::GeoUndef;
        toolWidgetManager.resetControls();
    }

    bool isTangentMethod() const
    {
        return constructionMethod() == ConstructionMethod::TwoTangent
            || constructionMethod() == ConstructionMethod::ThreeTangent;
    }

    /// Tangent methods: picking lines (all three steps for ThreeTangent, the first two for TwoTangent)
    bool isPickingLine() const
    {
        return state() == SelectMode::SeekFirst || state() == SelectMode::SeekSecond
            || (state() == SelectMode::SeekThird
                && constructionMethod() == ConstructionMethod::ThreeTangent);
    }

    /// A line as n·p + c = 0 (n a unit normal), with its segment's ends.
    struct Line2d
    {
        Base::Vector2d n, a, b;
        double c = 0.0;
    };

    bool lineOf(int geoId, Line2d& line)
    {
        const Part::Geometry* geo = getSketchObject()->getGeometry(geoId);
        if (!geo || !geo->is<Part::GeomLineSegment>()) {
            return false;
        }
        auto* segment = static_cast<const Part::GeomLineSegment*>(geo);
        const Base::Vector3d s = segment->getStartPoint();
        const Base::Vector3d e = segment->getEndPoint();
        line.a = Base::Vector2d(s.x, s.y);
        line.b = Base::Vector2d(e.x, e.y);
        Base::Vector2d u = line.b - line.a;
        if (u.Length() < Precision::Confusion()) {
            return false;
        }
        u.Normalize();
        line.n = Base::Vector2d(-u.y, u.x);
        line.c = -(line.n * line.a);
        return true;
    }

    /// The line under the pointer (a sketch line or an axis) not picked yet, else GeoUndef.
    int lineUnderPointer() const
    {
        const PreselectionData data = getPreselectionData();
        if (!data.isLine || data.geoId == Sketcher::GeoEnum::GeoUndef
            || std::ranges::find(tangentLines, data.geoId) != tangentLines.end()) {
            return Sketcher::GeoEnum::GeoUndef;
        }
        return data.geoId;
    }

    void updateTangentCircle(Base::Vector2d onSketchPos)
    {
        toolWidgetManager.drawPositionAtCursor(onSketchPos);
        radius = 0.0;
        if (isPickingLine()) {
            hoveredLine = lineUnderPointer();
            if (state() == SelectMode::SeekThird && hoveredLine != Sketcher::GeoEnum::GeoUndef) {
                placeThreeTangentCircle(hoveredLine, onSketchPos);  // the circle it would make
            }
        }
        else {
            placeTwoTangentCircle(onSketchPos);
        }
        CreateAndDrawShapeGeometry();
    }

    /// TwoTangent: the circle touching both lines, its center on the line halfway between them in
    /// the corner the pointer is in, nearest the pointer; or of the given radius in that corner.
    void placeTwoTangentCircle(Base::Vector2d pointer, double givenRadius = 0.0)
    {
        radius = 0.0;
        Line2d first, second;
        if (tangentLines.size() < 2 || !lineOf(tangentLines[0], first)
            || !lineOf(tangentLines[1], second)) {
            return;
        }
        // facing the pointer: its side of each line is positive
        const double s1 = first.n * pointer + first.c >= 0 ? 1.0 : -1.0;
        const double s2 = second.n * pointer + second.c >= 0 ? 1.0 : -1.0;
        const Base::Vector2d n1 = s1 * first.n;
        const Base::Vector2d n2 = s2 * second.n;
        const double c1 = s1 * first.c;
        const double c2 = s2 * second.c;
        const double cross = n1.x * n2.y - n1.y * n2.x;

        if (givenRadius > Precision::Confusion() && fabs(cross) > Precision::Confusion()) {
            // n1·p + c1 = n2·p + c2 = givenRadius
            const double r1 = givenRadius - c1;
            const double r2 = givenRadius - c2;
            centerPoint = Base::Vector2d((r1 * n2.y - n1.y * r2) / cross, (n1.x * r2 - r1 * n2.x) / cross);
            radius = givenRadius;
            return;
        }

        const Base::Vector2d q = n1 - n2;  // the halfway line: q·p + (c1 - c2) = 0
        if (q.Length() < Precision::Confusion()) {
            return;  // parallel, the pointer outside both
        }
        centerPoint = pointer - ((q * pointer + c1 - c2) / (q * q)) * q;
        const double distance = n1 * centerPoint + c1;
        radius = distance > Precision::Confusion() ? distance : 0.0;
    }

    /// ThreeTangent: of the circles touching the three lines (a triangle's inscribed and escribed
    /// ones), the one touching each within its segment if any, else the one nearest the pointer.
    void placeThreeTangentCircle(int third, Base::Vector2d pointer)
    {
        radius = 0.0;
        Line2d lines[3];
        if (tangentLines.size() < 2 || !lineOf(tangentLines[0], lines[0])
            || !lineOf(tangentLines[1], lines[1]) || !lineOf(third, lines[2])) {
            return;
        }
        auto det3 = [](double a1, double b1, double c1, double a2, double b2, double c2, double a3, double b3, double c3) {
            return a1 * (b2 * c3 - b3 * c2) - b1 * (a2 * c3 - a3 * c2) + c1 * (a2 * b3 - a3 * b2);
        };
        auto onSegments = [&lines](const Base::Vector2d& p) {
            for (const auto& line : lines) {
                const Base::Vector2d along = line.b - line.a;
                const double t = ((p - line.a) * along) / (along * along);
                if (t < -Precision::Confusion() || t > 1 + Precision::Confusion()) {
                    return false;
                }
            }
            return true;
        };
        bool bestInside = false;
        double bestDistance = 0.0;
        for (int signs = 0; signs < 8; ++signs) {  // which side of each line the center is on
            double s[3];
            for (int i = 0; i < 3; ++i) {
                s[i] = (signs & (1 << i)) ? -1.0 : 1.0;
            }
            // n_i·p + c_i = s_i r  ->  [n_i.x  n_i.y  -s_i] (x y r) = -c_i
            const auto& l = lines;
            const double d = det3(l[0].n.x, l[0].n.y, -s[0], l[1].n.x, l[1].n.y, -s[1], l[2].n.x, l[2].n.y, -s[2]);
            if (fabs(d) < Precision::Confusion()) {
                continue;
            }
            const double x = det3(-l[0].c, l[0].n.y, -s[0], -l[1].c, l[1].n.y, -s[1], -l[2].c, l[2].n.y, -s[2]) / d;
            const double y = det3(l[0].n.x, -l[0].c, -s[0], l[1].n.x, -l[1].c, -s[1], l[2].n.x, -l[2].c, -s[2]) / d;
            const double r = det3(l[0].n.x, l[0].n.y, -l[0].c, l[1].n.x, l[1].n.y, -l[1].c, l[2].n.x, l[2].n.y, -l[2].c) / d;
            if (r < Precision::Confusion()) {
                continue;
            }
            const Base::Vector2d center(x, y);
            const bool inside = onSegments(center);
            const double distance = (center - pointer).Length();
            if (radius == 0.0 || (inside && !bestInside)
                || (inside == bestInside && distance < bestDistance)) {
                centerPoint = center;
                radius = r;
                bestInside = inside;
                bestDistance = distance;
            }
        }
    }

private:
    Base::Vector2d centerPoint, firstPoint, secondPoint;
    double radius;
    bool isDiameter;

    // Tangent methods: the lines picked so far, and the one under the pointer
    std::vector<int> tangentLines;
    int hoveredLine = Sketcher::GeoEnum::GeoUndef;
};

template<>
auto DSHCircleControllerBase::getState(int labelindex) const
{
    using Method = DrawSketchHandlerCircle::ConstructionMethod;

    // Tangent methods: the size once the lines are picked (TwoTangent), none for ThreeTangent
    if (handler->isTangentMethod()) {
        switch (labelindex) {
            case OnViewParameter::First:
            case OnViewParameter::Second:
                return SelectMode::SeekFirst;  // not used: the first step picks a line
            case OnViewParameter::Third:
                return handler->constructionMethod() == Method::TwoTangent ? SelectMode::SeekThird
                                                                           : SelectMode::End;
            default:
                THROWM(Base::ValueError, "OnViewParameter index without an associated machine state")
        }
    }

    // Center and TwoRim: a point, then a size
    if (handler->constructionMethod() != DrawSketchHandlerCircle::ConstructionMethod::ThreeRim) {
        switch (labelindex) {
            case OnViewParameter::First:
            case OnViewParameter::Second:
                return SelectMode::SeekFirst;
                break;
            case OnViewParameter::Third:
                return SelectMode::SeekSecond;
                break;
            default:
                THROWM(Base::ValueError, "OnViewParameter index without an associated machine state")
        }
    }
    else {  // ConstructionMethod::ThreeRim
        switch (labelindex) {
            case OnViewParameter::First:
            case OnViewParameter::Second:
                return SelectMode::SeekFirst;
                break;
            case OnViewParameter::Third:
            case OnViewParameter::Fourth:
                return SelectMode::SeekSecond;
                break;
            case OnViewParameter::Fifth:
            case OnViewParameter::Sixth:
                return SelectMode::SeekThird;
                break;
            default:
                THROWM(Base::ValueError, "Label index without an associated machine state")
        }
    }
}

template<>
void DSHCircleController::configureToolWidget()
{
    if (!init) {  // Code to be executed only upon initialisation
        QStringList names = {
            QApplication::translate("Sketcher_CreateCircle", "Center"),
            QApplication::translate("Sketcher_CreateCircle", "3 rim points"),
            QApplication::translate("Sketcher_CreateCircle", "2 rim points (diameter)"),
            QApplication::translate("Sketcher_CreateCircle", "Tangent to 2 lines"),
            QApplication::translate("Sketcher_CreateCircle", "Tangent to 3 lines")
        };
        toolWidget->setComboboxElements(WCombobox::FirstCombo, names);
        for (int i : {3, 4}) {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                i,
                Gui::BitmapFactory().iconFromTheme(
                    handler->isConstructionMode() ? "Sketcher_CreateCircle_Constr" : "Sketcher_CreateCircle"
                )
            );
        }

        if (handler->isConstructionMode()) {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateCircle_Constr")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointCircle_Constr")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                2,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointCircle_Constr")
            );
        }
        else {
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                0,
                Gui::BitmapFactory().iconFromTheme("Sketcher_CreateCircle")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                1,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointCircle")
            );
            toolWidget->setComboboxItemIcon(
                WCombobox::FirstCombo,
                2,
                Gui::BitmapFactory().iconFromTheme("Sketcher_Create3PointCircle")
            );
        }


        ParameterGrp::handle hGrp = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/Mod/Sketcher/dimensioning"
        );
        bool dimensioningDiameter = hGrp->GetBool("DimensioningDiameter", true);
        bool dimensioningRadius = hGrp->GetBool("DimensioningRadius", true);

        if (dimensioningRadius && !dimensioningDiameter) {
            handler->isDiameter = false;
        }
    }

    onViewParameters[OnViewParameter::First]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
    onViewParameters[OnViewParameter::Second]->setLabelType(Gui::SoDatumLabel::DISTANCEY);

    if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::ThreeRim) {
        onViewParameters[OnViewParameter::Third]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
        onViewParameters[OnViewParameter::Fourth]->setLabelType(Gui::SoDatumLabel::DISTANCEY);

        onViewParameters[OnViewParameter::Fifth]->setLabelType(Gui::SoDatumLabel::DISTANCEX);
        onViewParameters[OnViewParameter::Sixth]->setLabelType(Gui::SoDatumLabel::DISTANCEY);
    }
    else {
        ParameterGrp::handle hGrp = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/Mod/Sketcher/dimensioning"
        );
        bool dimensioningDiameter = hGrp->GetBool("DimensioningDiameter", true);
        bool dimensioningRadius = hGrp->GetBool("DimensioningRadius", true);

        if (dimensioningRadius && !dimensioningDiameter) {
            onViewParameters[OnViewParameter::Third]->setLabelType(
                Gui::SoDatumLabel::RADIUS,
                Gui::EditableDatumLabel::Function::Dimensioning
            );
        }
        else {
            onViewParameters[OnViewParameter::Third]->setLabelType(
                Gui::SoDatumLabel::DIAMETER,
                Gui::EditableDatumLabel::Function::Dimensioning
            );
        }
    }
}

template<>
void DSHCircleControllerBase::doEnforceControlParameters(Base::Vector2d& onSketchPos)
{
    if (handler->isTangentMethod()) {
        // Lines are picked, not typed. TwoTangent's typed size puts the center where a circle of
        // that size touches both lines, in the corner the pointer is in.
        auto& thirdParam = onViewParameters[OnViewParameter::Third];
        if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::TwoTangent
            && handler->state() == SelectMode::SeekThird && thirdParam->isSet) {
            const double size = thirdParam->getValue();
            if (size < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                unsetOnViewParameter(thirdParam.get());
                return;
            }
            handler->placeTwoTangentCircle(onSketchPos, handler->isDiameter ? size / 2 : size);
            if (handler->radius > Precision::Confusion()) {
                onSketchPos = handler->centerPoint;  // on the halfway line: stays there
            }
        }
        return;
    }

    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (firstParam->isSet) {
                onSketchPos.x = firstParam->getValue();
            }

            if (secondParam->isSet) {
                onSketchPos.y = secondParam->getValue();
            }
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];

            if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::Center) {
                if (thirdParam->isSet) {
                    double radius = (handler->isDiameter ? 0.5 : 1) * thirdParam->getValue();
                    if (radius < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                        unsetOnViewParameter(thirdParam.get());
                        return;
                    }

                    auto dir = (onSketchPos - handler->centerPoint);

                    if (dir.Length() < Precision::Confusion()) {
                        dir.x = 1.0;  // if direction null, default to (1,0)
                    }

                    onSketchPos = handler->centerPoint + radius * dir.Normalize();
                }
            }
            else if (handler->constructionMethod()
                     == DrawSketchHandlerCircle::ConstructionMethod::TwoRim) {
                if (thirdParam->isSet) {  // the second point a diameter from the first
                    double diameter = (handler->isDiameter ? 1 : 2) * thirdParam->getValue();
                    if (diameter < Precision::Confusion() && thirdParam->hasFinishedEditing) {
                        unsetOnViewParameter(thirdParam.get());
                        return;
                    }

                    auto dir = (onSketchPos - handler->firstPoint);

                    if (dir.Length() < Precision::Confusion()) {
                        dir.x = 1.0;  // if direction null, default to (1,0)
                    }

                    onSketchPos = handler->firstPoint + diameter * dir.Normalize();
                }
            }
            else {
                auto& fourthParam = onViewParameters[OnViewParameter::Fourth];
                if (thirdParam->isSet) {
                    onSketchPos.x = thirdParam->getValue();
                }

                if (fourthParam->isSet) {
                    onSketchPos.y = fourthParam->getValue();
                }

                if (thirdParam->hasFinishedEditing && fourthParam->hasFinishedEditing
                    && (onSketchPos - handler->firstPoint).Length() < Precision::Confusion()) {
                    unsetOnViewParameter(thirdParam.get());
                    unsetOnViewParameter(fourthParam.get());
                }
            }
        } break;
        case SelectMode::SeekThird: {  // 3 rims only
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            if (fifthParam->isSet) {
                onSketchPos.x = fifthParam->getValue();
            }

            if (sixthParam->isSet) {
                onSketchPos.y = sixthParam->getValue();
            }
            if (fifthParam->hasFinishedEditing && sixthParam->hasFinishedEditing
                && areCollinear(handler->firstPoint, handler->secondPoint, onSketchPos)) {
                unsetOnViewParameter(fifthParam.get());
                unsetOnViewParameter(sixthParam.get());
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHCircleController::adaptParameters(Base::Vector2d onSketchPos)
{
    if (handler->isTangentMethod()) {
        // TwoTangent shows the size while it's placed; nothing else to show while picking lines
        auto& thirdParam = onViewParameters[OnViewParameter::Third];
        if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::TwoTangent
            && handler->state() == SelectMode::SeekThird && handler->radius > Precision::Confusion()) {
            if (!thirdParam->isSet) {
                setOnViewParameterValue(
                    OnViewParameter::Third,
                    handler->radius * (handler->isDiameter ? 2 : 1)
                );
            }
            const Base::Vector2d out(handler->radius, 0.0);
            thirdParam->setPoints(
                toVector3d(handler->isDiameter ? handler->centerPoint - out : handler->centerPoint),
                toVector3d(handler->centerPoint + out)
            );
        }
        return;
    }

    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (!firstParam->isSet) {
                setOnViewParameterValue(OnViewParameter::First, onSketchPos.x);
            }

            if (!secondParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Second, onSketchPos.y);
            }

            bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
            firstParam->setLabelAutoDistanceReverse(!sameSign);
            secondParam->setLabelAutoDistanceReverse(sameSign);
            firstParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
            secondParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];

            if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::Center) {
                ParameterGrp::handle hGrp = App::GetApplication().GetParameterGroupByPath(
                    "User parameter:BaseApp/Preferences/Mod/Sketcher/dimensioning"
                );
                bool dimDiameter = hGrp->GetBool("DimensioningDiameter", true);
                bool dimRadius = hGrp->GetBool("DimensioningRadius", true);
                bool useRadius = dimRadius && !dimDiameter;

                if (!thirdParam->isSet) {
                    double val = handler->radius * (useRadius ? 1 : 2);
                    setOnViewParameterValue(OnViewParameter::Third, val);
                }

                Base::Vector3d start = toVector3d(handler->centerPoint);
                Base::Vector3d end = toVector3d(onSketchPos);
                if (!useRadius) {
                    start = toVector3d(handler->centerPoint - (onSketchPos - handler->centerPoint));
                }

                thirdParam->setPoints(start, end);
            }
            else if (handler->constructionMethod()
                     == DrawSketchHandlerCircle::ConstructionMethod::TwoRim) {
                if (!thirdParam->isSet) {
                    setOnViewParameterValue(
                        OnViewParameter::Third,
                        handler->radius * (handler->isDiameter ? 2 : 1)
                    );
                }
                thirdParam->setPoints(
                    toVector3d(handler->isDiameter ? handler->firstPoint : handler->centerPoint),
                    toVector3d(onSketchPos)
                );
            }
            else {
                auto& fourthParam = onViewParameters[OnViewParameter::Fourth];
                if (!thirdParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Third, onSketchPos.x);
                }

                if (!fourthParam->isSet) {
                    setOnViewParameterValue(OnViewParameter::Fourth, onSketchPos.y);
                }

                bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
                thirdParam->setLabelAutoDistanceReverse(!sameSign);
                fourthParam->setLabelAutoDistanceReverse(sameSign);
                thirdParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
                fourthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
            }
        } break;
        case SelectMode::SeekThird: {  // 3 rims only
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            if (!fifthParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Fifth, onSketchPos.x);
            }

            if (!sixthParam->isSet) {
                setOnViewParameterValue(OnViewParameter::Sixth, onSketchPos.y);
            }

            bool sameSign = onSketchPos.x * onSketchPos.y > 0.;
            fifthParam->setLabelAutoDistanceReverse(!sameSign);
            sixthParam->setLabelAutoDistanceReverse(sameSign);
            fifthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
            sixthParam->setPoints(Base::Vector3d(), toVector3d(onSketchPos));
        } break;
        default:
            break;
    }
}

template<>
void DSHCircleController::computeNextDrawSketchHandlerMode()
{
    if (handler->isTangentMethod()) {
        // lines are picked with clicks; TwoTangent ends when its size is typed
        if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::TwoTangent
            && handler->state() == SelectMode::SeekThird
            && onViewParameters[OnViewParameter::Third]->hasFinishedEditing
            && handler->radius > Precision::Confusion()) {
            handler->setNextState(SelectMode::End);
        }
        return;
    }

    switch (handler->state()) {
        case SelectMode::SeekFirst: {
            auto& firstParam = onViewParameters[OnViewParameter::First];
            auto& secondParam = onViewParameters[OnViewParameter::Second];

            if (firstParam->hasFinishedEditing && secondParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::SeekSecond);
            }
        } break;
        case SelectMode::SeekSecond: {
            auto& thirdParam = onViewParameters[OnViewParameter::Third];

            if (thirdParam->hasFinishedEditing
                && handler->constructionMethod()
                    != DrawSketchHandlerCircle::ConstructionMethod::ThreeRim) {

                handler->setNextState(SelectMode::End);
            }
            else if (onViewParameters.size() > 3) {
                auto& fourthParam = onViewParameters[OnViewParameter::Fourth];
                if ((thirdParam->hasFinishedEditing || fourthParam->hasFinishedEditing)
                    && handler->constructionMethod()
                        == DrawSketchHandlerCircle::ConstructionMethod::ThreeRim) {

                    handler->setNextState(SelectMode::SeekThird);
                }
            }
        } break;
        case SelectMode::SeekThird: {
            auto& fifthParam = onViewParameters[OnViewParameter::Fifth];
            auto& sixthParam = onViewParameters[OnViewParameter::Sixth];

            if (fifthParam->hasFinishedEditing && sixthParam->hasFinishedEditing) {
                handler->setNextState(SelectMode::End);
            }
        } break;
        default:
            break;
    }
}

template<>
void DSHCircleController::doConstructionMethodChanged()
{
    // Just update hints - combobox already handled by framework
    handler->updateHint();
}

template<>
void DSHCircleController::addConstraints()
{
    if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::Center) {
        int firstCurve = handler->getHighestCurveIndex();

        auto x0 = onViewParameters[OnViewParameter::First]->getValue();
        auto y0 = onViewParameters[OnViewParameter::Second]->getValue();

        auto x0set = onViewParameters[OnViewParameter::First]->isSet;
        auto y0set = onViewParameters[OnViewParameter::Second]->isSet;
        auto radiusSet = onViewParameters[OnViewParameter::Third]->isSet;

        using namespace Sketcher;

        auto constraintx0 = [&]() {
            ConstraintToAttachment(
                GeoElementId(firstCurve, PointPos::mid),
                GeoElementId::VAxis,
                x0,
                handler->sketchgui->getObject()
            );
        };

        auto constrainty0 = [&]() {
            ConstraintToAttachment(
                GeoElementId(firstCurve, PointPos::mid),
                GeoElementId::HAxis,
                y0,
                handler->sketchgui->getObject()
            );
        };

        auto constraintradius = [&]() {
            if (handler->isDiameter) {
                Gui::cmdAppObjectArgs(
                    handler->sketchgui->getObject(),
                    "addConstraint(Sketcher.Constraint('Diameter',%d,%f)) ",
                    firstCurve,
                    handler->radius * 2
                );
            }
            else {
                Gui::cmdAppObjectArgs(
                    handler->sketchgui->getObject(),
                    "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
                    firstCurve,
                    handler->radius
                );
            }

            const std::vector<Sketcher::Constraint*>& ConStr
                = handler->sketchgui->getSketchObject()->Constraints.getValues();
            int index = static_cast<int>(ConStr.size()) - 1;
            handler->moveConstraint(index, prevCursorPosition);
        };

        // NOTE: if AutoConstraints is empty, we can add constraints directly without any diagnose.
        // No diagnose was run.
        if (handler->AutoConstraints.empty()) {
            if (x0set) {
                constraintx0();
            }

            if (y0set) {
                constrainty0();
            }

            if (radiusSet) {
                constraintradius();
            }
        }
        else {  // There is a valid diagnose.
            auto startpointinfo = handler->getPointInfo(GeoElementId(firstCurve, PointPos::mid));

            // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
            // always be set
            if (x0set && startpointinfo.isXDoF()) {
                constraintx0();

                handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters
                                                         // after each constraint addition

                startpointinfo = handler->getPointInfo(
                    GeoElementId(firstCurve, PointPos::mid)
                );  // get updated point position
            }

            // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
            // always be set
            if (y0set && startpointinfo.isYDoF()) {
                constrainty0();

                handler->diagnoseWithAutoConstraints();  // ensure we have recalculated parameters
                                                         // after each constraint addition
            }

            auto edgeinfo = handler->getEdgeInfo(firstCurve);
            auto circle = static_cast<SolverGeometryExtension::Circle&>(edgeinfo);

            // if Autoconstraints is empty we do not have a diagnosed system and the parameter will
            // always be set
            if (radiusSet && circle.isRadiusDoF()) {
                constraintradius();
            }
        }
    }
    else if (handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::TwoRim
             || handler->constructionMethod() == DrawSketchHandlerCircle::ConstructionMethod::TwoTangent) {
        // A typed diameter (or radius) becomes one, unless the clicked points already set it.
        if (!onViewParameters[OnViewParameter::Third]->isSet) {
            return;
        }
        int circleId = handler->getHighestCurveIndex();
        if (!handler->AutoConstraints.empty()) {
            auto edgeinfo = handler->getEdgeInfo(circleId);
            auto circle = static_cast<Sketcher::SolverGeometryExtension::Circle&>(edgeinfo);
            if (!circle.isRadiusDoF()) {
                return;
            }
        }
        Gui::cmdAppObjectArgs(
            handler->sketchgui->getObject(),
            handler->isDiameter ? "addConstraint(Sketcher.Constraint('Diameter',%d,%f)) "
                                : "addConstraint(Sketcher.Constraint('Radius',%d,%f)) ",
            circleId,
            handler->isDiameter ? handler->radius * 2 : handler->radius
        );
        const std::vector<Sketcher::Constraint*>& constraints
            = handler->sketchgui->getSketchObject()->Constraints.getValues();
        handler->moveConstraint(static_cast<int>(constraints.size()) - 1, prevCursorPosition);
    }
    // No constraint possible for 3 rim circle.
}

}  // namespace SketcherGui
