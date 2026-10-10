package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestMode_Cases(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{
			name:    "single element",
			input:   Float64Data{5},
			want:    []float64{5},
			wantErr: nil,
		},
		{
			name:    "empty input",
			input:   Float64Data{},
			want:    nil,
			wantErr: EmptyInputErr,
		},
		{
			name:    "all distinct",
			input:   Float64Data{3, 1, 2},
			want:    []float64{},
			wantErr: nil,
		},
		{
			name:    "all same",
			input:   Float64Data{2, 2, 2},
			want:    []float64{2},
			wantErr: nil,
		},
		{
			name:    "multiple modes partial",
			input:   Float64Data{1, 1, 2, 2, 3},
			want:    []float64{1, 2},
			wantErr: nil,
		},
		{
			name:    "multiple modes all",
			input:   Float64Data{1, 1, 2, 2},
			want:    []float64{},
			wantErr: nil,
		},
		{
			name:    "single mode with others",
			input:   Float64Data{1, 1, 2, 3},
			want:    []float64{1},
			wantErr: nil,
		},
		{
			name:    "final sequence greater",
			input:   Float64Data{1, 2, 2, 2},
			want:    []float64{2},
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Mode(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if got != nil {
					t.Fatalf("expected nil result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.want == nil {
				if got != nil {
					t.Fatalf("expected nil result, got %v", got)
				}
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d elements, got %d (%v)", len(tc.want), len(got), got)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
