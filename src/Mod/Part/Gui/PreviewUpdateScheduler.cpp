// SPDX-License-Identifier: LGPL-2.1-or-later
/****************************************************************************
 *                                                                          *
 *   Copyright (c) 2026 Kacper Donat <kacper@kadet.net>                     *
 *                                                                          *
 *   This file is part of FreeCAD.                                          *
 *                                                                          *
 *   FreeCAD is free software: you can redistribute it and/or modify it     *
 *   under the terms of the GNU Lesser General Public License as            *
 *   published by the Free Software Foundation, either version 2.1 of the   *
 *   License, or (at your option) any later version.                        *
 *                                                                          *
 *   FreeCAD is distributed in the hope that it will be useful, but         *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of             *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
 *   Lesser General Public License for more details.                        *
 *                                                                          *
 *   You should have received a copy of the GNU Lesser General Public       *
 *   License along with FreeCAD. If not, see                                *
 *   <https://www.gnu.org/licenses/>.                                       *
 *                                                                          *
 ***************************************************************************/

#include "PreviewUpdateScheduler.h"

#include <QTimer>

#include <App/Application.h>
#include <App/Document.h>
#include <Base/Console.h>
#include <Base/Exception.h>
#include <Base/Sequencer.h>

#include <Standard_Failure.hxx>

FC_LOG_LEVEL_INIT("Part", true, true);

using namespace PartGui;

QtPreviewUpdateScheduler::QtPreviewUpdateScheduler(QObject* parent)
    : QObject(parent)
{}

void QtPreviewUpdateScheduler::schedulePreviewRecompute(App::DocumentObject* object)
{
    if (!object) {
        return;
    }

    toBeUpdated.emplace(object);

    // if method call was already scheduled there is no need to queue another one
    if (scheduled) {
        return;
    }

    scheduled = true;

    QMetaObject::invokeMethod(this, &QtPreviewUpdateScheduler::flush, Qt::QueuedConnection);
}

namespace
{
// Studio (CORE_PATCHES.md): whether a recompute, or a long operation showing a progress bar, is under way.
bool busy()
{
    if (Base::SequencerBase::Instance().isRunning()) {
        return true;
    }
    for (App::Document* doc : App::GetApplication().getDocuments()) {
        if (doc->testStatus(App::Document::Recomputing)) {
            return true;
        }
    }
    return false;
}
}  // namespace

void QtPreviewUpdateScheduler::flush()
{
    // Studio (CORE_PATCHES.md): not during a recompute or a progress bar. A long recompute's progress bar
    // keeps the window updating, and a preview computed then starts a second OpenCASCADE boolean inside the
    // first one, which waits for the first one's lock forever: the Hole panel's Tap drill on a filleted part
    // froze the app. Try again shortly; `scheduled` stays set, so requests made meanwhile join this one.
    if (busy()) {
        QTimer::singleShot(100, this, &QtPreviewUpdateScheduler::flush);
        return;
    }

    scheduled = false;

    // use std::exchange to prevent race conditions on updates that could occur during a flush
    for (auto objects = std::exchange(this->toBeUpdated, {}); auto& object : objects) {
        if (object.expired()) {
            continue;
        }

        if (auto* previewExtension = object->getExtensionByType<Part::PreviewExtension>(true)) {
            try {
                previewExtension->updatePreview();
            }
            catch (Standard_Failure& e) {
                FC_ERR("Preview update failed: " << e.GetMessageString());
            }
            catch (Base::Exception& e) {
                FC_ERR("Preview update failed: " << e.what());
            }
        }
    }
}

#include "moc_PreviewUpdateScheduler.cpp"
