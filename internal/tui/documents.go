package tui

import (
	"context"
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/hev/tpuff/internal/client"
	"github.com/turbopuffer/turbopuffer-go"
)

type documentsLoadedMsg struct {
	rows []map[string]any
}

type documentsErrMsg struct {
	err error
}

type documentsModel struct {
	namespace  string
	rows       []map[string]any
	cursor     int
	loading    bool
	err        error
	page       int
	pageSize   int
	schemaDict map[string]any
}

func newDocumentsModel(namespace string) documentsModel {
	return documentsModel{
		namespace: namespace,
		loading:   true,
		pageSize:  50,
	}
}

func (m documentsModel) init(region string, schemaDict map[string]any) tea.Cmd {
	ns := m.namespace
	pageSize := m.pageSize
	return func() tea.Msg {
		return fetchDocuments(ns, region, pageSize, schemaDict)
	}
}

func fetchDocuments(namespace, region string, topK int, schemaDict map[string]any) tea.Msg {
	ctx := context.Background()
	ns, err := client.GetNamespace(namespace, region)
	if err != nil {
		return documentsErrMsg{err: err}
	}

	// Get schema to find vector attribute
	if schemaDict == nil {
		md, err := ns.Metadata(ctx, turbopuffer.NamespaceMetadataParams{})
		if err != nil {
			return documentsErrMsg{err: err}
		}
		schemaDict = make(map[string]any)
		for k, v := range md.Schema {
			schemaDict[k] = v
		}
	}

	vecAttr, dims := extractVectorInfo(schemaDict)
	if vecAttr == "" {
		return documentsErrMsg{err: fmt.Errorf("no vector attribute found in namespace schema")}
	}

	zeroVec := make([]float32, dims)
	result, err := ns.Query(ctx, turbopuffer.NamespaceQueryParams{
		RankBy:            turbopuffer.NewRankByVector(vecAttr, zeroVec),
		TopK:              turbopuffer.Int(int64(topK)),
		ExcludeAttributes: []string{vecAttr},
	})
	if err != nil {
		return documentsErrMsg{err: err}
	}

	rows := make([]map[string]any, len(result.Rows))
	for i, r := range result.Rows {
		rows[i] = map[string]any(r)
	}
	return documentsLoadedMsg{rows: rows}
}

func (m documentsModel) selected() map[string]any {
	if m.cursor < 0 || m.cursor >= len(m.rows) {
		return nil
	}
	return m.rows[m.cursor]
}

func (m documentsModel) update(msg tea.Msg, region string, schemaDict map[string]any) (documentsModel, tea.Cmd) {
	switch msg := msg.(type) {
	case documentsLoadedMsg:
		m.rows = msg.rows
		m.loading = false
		m.schemaDict = schemaDict
		return m, nil
	case documentsErrMsg:
		m.err = msg.err
		m.loading = false
		return m, nil
	case tea.KeyMsg:
		switch {
		case msg.String() == "j" || msg.String() == "down":
			if m.cursor < len(m.rows)-1 {
				m.cursor++
			}
		case msg.String() == "k" || msg.String() == "up":
			if m.cursor > 0 {
				m.cursor--
			}
		case msg.String() == "G":
			m.cursor = max(0, len(m.rows)-1)
		case msg.String() == "g":
			m.cursor = 0
		}
	}
	return m, nil
}

func (m documentsModel) view(width, height int) string {
	if m.loading {
		return loadingStyle.Render(fmt.Sprintf("Loading documents from %s...", m.namespace))
	}
	if m.err != nil {
		return errorStyle.Render(fmt.Sprintf("Error: %s\n\n", m.err)) +
			helpStyle.Render("esc back • q quit")
	}
	if len(m.rows) == 0 {
		return fmt.Sprintf("No documents found in %s\n\n", m.namespace) +
			helpStyle.Render("esc back • q quit")
	}

	var b strings.Builder

	// Header
	title := fmt.Sprintf(" %s (%d docs) ", m.namespace, len(m.rows))
	b.WriteString(headerStyle.Render(title))
	b.WriteString("\n\n")

	// Column headers
	idW := 24
	if width > 80 {
		idW = 32
	}
	contentsW := width - idW - 8
	if contentsW < 20 {
		contentsW = 40
	}

	header := fmt.Sprintf("  %-*s %s", idW, "ID", "Contents")
	b.WriteString(columnHeaderStyle.Render(header))
	b.WriteString("\n")

	// Rows with scrolling
	maxRows := height - 6
	offset := 0
	if m.cursor >= maxRows {
		offset = m.cursor - maxRows + 1
	}

	for i := offset; i < len(m.rows) && i < offset+maxRows; i++ {
		row := m.rows[i]
		id := fmt.Sprintf("%v", row["id"])
		id = truncate(id, idW)
		preview := docPreviewLine(row, m.schemaDict, contentsW)

		line := fmt.Sprintf("  %-*s %s", idW, id, preview)
		if i == m.cursor {
			b.WriteString(selectedStyle.Render("▸ " + line[2:]))
		} else {
			b.WriteString(normalStyle.Render(line))
		}
		b.WriteString("\n")
	}

	// Help
	b.WriteString("\n")
	b.WriteString(helpStyle.Render("↑/k up • ↓/j down • enter preview • s schema • esc back"))

	return b.String()
}
