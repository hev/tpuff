package tui

import (
	"fmt"
	"strings"
	"time"

	"github.com/atotto/clipboard"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
)

type previewModel struct {
	docID    string
	content  string
	viewport viewport.Model
	ready    bool

	// transient status (copy feedback)
	toast       string
	toastExpiry time.Time
}

func newPreviewModel(docID, content string) previewModel {
	return previewModel{
		docID:   docID,
		content: content,
	}
}

func (m *previewModel) setSize(width, height int) {
	headerH := 4
	footerH := 3
	w := width - 4
	h := height - headerH - footerH
	if w < 20 {
		w = 20
	}
	if h < 5 {
		h = 5
	}
	if !m.ready {
		m.viewport = viewport.New(w, h)
		m.viewport.SetContent(m.content)
		m.ready = true
	} else {
		m.viewport.Width = w
		m.viewport.Height = h
	}
}

func (m previewModel) update(msg tea.Msg) previewModel {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.setSize(msg.Width, msg.Height)
		return m
	case tea.KeyMsg:
		if msg.String() == "y" {
			if err := clipboard.WriteAll(m.content); err != nil {
				m.toast = "copy failed: " + err.Error()
			} else {
				m.toast = "Copied document to clipboard"
			}
			m.toastExpiry = time.Now().Add(2 * time.Second)
			return m
		}
	}
	if m.ready {
		var cmd tea.Cmd
		m.viewport, cmd = m.viewport.Update(msg)
		_ = cmd
	}
	return m
}

func (m previewModel) view(width, height int) string {
	if !m.ready {
		m.setSize(width, height)
	}

	var b strings.Builder

	title := fmt.Sprintf(" Document: %s ", m.docID)
	b.WriteString(headerStyle.Render(title))
	b.WriteString("\n\n")

	b.WriteString(m.viewport.View())
	b.WriteString("\n\n")

	scrollPct := fmt.Sprintf("%3.f%%", m.viewport.ScrollPercent()*100)
	help := fmt.Sprintf("↑/k up • ↓/j down • enter full view • y copy • esc back  %s", scrollPct)
	if m.toast != "" && time.Now().Before(m.toastExpiry) {
		b.WriteString(statusStyle.Render(m.toast))
		b.WriteString("\n")
	}
	b.WriteString(helpStyle.Render(help))

	return b.String()
}
